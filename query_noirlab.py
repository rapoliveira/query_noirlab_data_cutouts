#!/usr/bin/env python3
"""
Code to make queries in the NOIRLab database, specially from the SMASH
survey, using the astroquery and pyvo libraries.

The YAML file query_settings.yaml allows to select a SMASH field (1-247),
a cluster (coordinates from Bica catalogues or Vizier) or a single coordinate,
as well as specifying the search radius. A file with a list of coordinates
is also allowed as input.
"""

# Standard library imports
from datetime import datetime
from itertools import chain
import os
import sys
import warnings

# Third-party imports
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table, vstack
from astropy.utils.exceptions import AstropyWarning
from astroquery.utils import parse_coordinates
import numpy as np
import pyvo as vo
import yaml


def main():

    path = os.path.dirname(os.path.realpath(__file__))
    input_file = sys.argv[1]
    with open(input_file, 'r', encoding='utf-8') as data:
        settings = yaml.safe_load(data)
    warnings.simplefilter('ignore', AstropyWarning)

    data_name = settings['schema_name'] + '.' + settings['table_name']
    validate_survey(data_name)
    shape, size = validate_shape_and_size(settings)
    if settings['type'] == "SMASH field":
        info = [get_smash_field(path, settings)]
    elif settings['type'] == "cluster":
        info = [get_cluster_coords(path, settings)]
    elif settings['type'] == "coordinates":
        info = [validate_coordinates(settings['object'])]
    elif settings['type'] == 'list of coords':
        info = read_coords_list(path, settings)
    else:
        raise NotImplementedError("Type must be 'SMASH field' or 'cluster'.")

    # This line needs to be fixed for box shape!!!
    # fname_suffix = shape[0] + str(size).replace('.', 'p') + "deg"
    fname_suffix = shape[0] + str(size[0]).replace('.', 'p') + "deg"
    for item in info[:1]:
        table = download_data(data_name, item[0], item[1], shape, size)
        fname = settings["schema_name"] + item[2] + fname_suffix
        table = save_cat(table, fname, path)
    print()


def validate_survey(data_full_name):
    """
    Validate if the survey and table name is available in NOIRLab.
    """
    schema_name = data_full_name.split('.')[0]
    available_surveys = Table.read("tables/available_surveys.txt",
                                   format='ascii.no_header')
    check_1 = schema_name in available_surveys['col1']

    service = vo.dal.TAPService('https://datalab.noirlab.edu/tap')
    adql = """SELECT *
    FROM tap_schema.tables
    WHERE schema_name = '%s'
    """ % schema_name
    result_set = service.search(adql, maxrec=100000)
    check_2 = data_full_name in result_set['table_name'].data

    if not check_1 or not check_2:
        print(f"Survey {data_full_name} not available!")
        sys.exit()


def validate_shape_and_size(settings):
    """
    Validate and return the shape and size inputs.
    """
    shape = settings.get('shape', 'circle').lower()
    if shape not in ['circle', 'box']:
        raise ValueError("Shape must be 'circle' or 'box'.")

    region_size = settings['region_size']
    if isinstance(region_size, (int, float)):
        values = [region_size]
    elif isinstance(region_size, (list, tuple)):
        values = [v for x in region_size
                  for v in (x if isinstance(x, (list, tuple)) else [x])]
    else:
        raise TypeError("region_size must be a number or list of numbers.")

    if not all(isinstance(v, (int, float)) and 0 < v <= 1.5 for v in values):
        raise ValueError("region_size values must be between 0 and 1.5 deg.")

    return shape, region_size


def get_smash_field(path, settings):
    """
    Get RA, DEC, filename and message for a given SMASH field.
    """
    path = os.path.join(path, settings['tabs_path'], 'TAP-List-of-Fields.fits')
    fields = Table.read(path, format='fits')
    if int(settings['object']) not in fields['fieldid']:
        raise ValueError(f"Field {settings['object']} not available!")
    line = fields[fields['fieldid'] == settings['object']]

    id, ra, dec = line['fieldid'].item(), line['ra'].item(), line['dec'].item()
    fname = f"_TAP_f{id}_"
    settings['object'] = "Field " + str(id)

    return (ra, dec, fname)


def get_cluster_coords(path, settings):
    """
    Get coordinates of a cluster from Bica catalogues.

    To-Do: implement Harris catalogue, and then a Vizier search if the
    cluster is not found.
    """
    path = os.path.join(path, settings['tabs_path'])
    bica_08 = Table.read(os.path.join(path, "Bica08-LMC.fits"), format='fits')
    bica_20 = Table.read(os.path.join(path, "Bica20-tab2.fits"), format='fits')
    sel_cols = ["Names", "_RAJ2000", "_DEJ2000"]
    bicao = vstack([bica_08[sel_cols], bica_20[sel_cols]])

    names = bicao['Names']
    names = [n.strip().split(',') for n in names]
    names = np.array(names, dtype="object")
    obj_id = settings['object']
    if obj_id not in chain(*names):
        msg = f"Cluster {obj_id} not available!"
        raise NotImplementedError(msg + " Vizier search will be implemented.")

    idx = np.array([obj_id in item for item in names])
    ra = float(bicao['_RAJ2000'][idx].item())
    dec = float(bicao['_DEJ2000'][idx].item())
    fname = f"_{obj_id.replace(' ','')}_"

    return (ra, dec, fname)


def validate_coordinates(coord_str):
    """
    Validate and return RA, DEC, and filename for given coordinates.
    """
    coord_str = coord_str.strip()
    if coord_str.count(' ') >= 3 or coord_str.count(':') >= 2:
        coord = SkyCoord(coord_str, unit=(u.hourangle, u.deg))
    else:
        coord = parse_coordinates(coord_str)

    ra_str = coord.ra.to_string(unit=u.hour, sep='', pad=True, precision=2)
    dec_str = coord.dec.to_string(unit=u.deg,  sep='', pad=True, precision=1,
                                  alwayssign=True)
    fname = "_J" + ra_str.replace('.', 'p') + dec_str.replace('.', 'p') + "_"

    return (round(coord.ra.deg, 5), round(coord.dec.deg, 5), fname)


def read_coords_list(path, settings):
    """
    Read a list of coordinates from a file and return a list with RA, DEC,
    and filename for each coordinate.
    """
    path = os.path.join(path, settings['object'])
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File {settings['object']} not found!")
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    info_lst = []
    for line in lines:
        if line.strip() and not line.startswith('#'):
            info_lst.append(validate_coordinates(line))

    return info_lst


def download_data(db, RA, DEC, shape, size):
    """
    Download data from the NOIRLab database, using the service.search()
    function from the pyvo library.

    To-Do:
    - Check the other download options for longer queries;
    - Add other field shapes (e.g. ring, box, polygon...);
    - Simplify and add documentation...
    # NOIRLAB API: https://astroarchive.noirlab.edu/api/docs/
    # VO-TapService (https://pyvo.readthedocs.io/en/stable/)
    """
    start1 = datetime.now()
    service = vo.dal.TAPService('https://datalab.noirlab.edu/tap')

    if shape == "circle":
        adql = '''SELECT *
        FROM %s
            WHERE
                't'= Q3C_RADIAL_QUERY(ra,dec,%.5f,%.5f,%.3f)
        ''' % (db, RA, DEC, size)
    elif shape == "box":
        delta_ra = size[0] / np.cos(np.radians(DEC))
        adql = f"""
        SELECT *
        FROM {db}
        WHERE
            ra BETWEEN {RA - delta_ra} AND {RA + delta_ra}
            AND dec BETWEEN {DEC - size[1]} AND {DEC + size[1]}
        """
    result_set = service.search(adql, maxrec=100000)

    sec_column = np.zeros(len(result_set))
    for i in range(len(result_set)):
        sec_column[i] = result_set[i]['ra']
    astropyT = result_set.table

    delta_t1 = (datetime.now()-start1).seconds
    print(delta_t1, 'seconds')

    return astropyT


def save_cat(table, fname, prefix):
    """
    Update units and save catalog as a FITS file using AstroPy.

    AstroPy units: https://docs.astropy.org/en/stable/units/
    """
    for col in table.colnames:
        if table[col].unit == 'None':
            table[col].unit = u.dimensionless_unscaled
        elif table[col].unit == 'Degrees':
            table[col].unit = u.si.degree
        elif table[col].unit == 'degrees':
            table[col].unit = u.si.degree
        elif table[col].unit == 'Magnitude':
            table[col].unit = u.mag

    if os.path.isdir(prefix):
        if not os.path.isdir(f'{prefix}/catalogs/'):
            os.mkdir(f'{prefix}/catalogs/')
        table.write(f'{prefix}/catalogs/{fname}.fits', format='fits',
                    overwrite=True)
        print(f'Catalog saved as \"{prefix}/{fname}.fits\"')
    else:
        print('Catalog not saved: directory does not exist!')

    return table


if __name__ == '__main__':
    main()
