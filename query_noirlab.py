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
from astropy.table import Table, vstack
from astropy.utils.exceptions import AstropyWarning
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
    rad = validate_radius(settings['radius'])
    if settings['type'] == "SMASH field":
        info = get_smash_field(path, settings, rad)
    elif settings['type'] == "cluster":
        info = get_cluster_coords(path, settings, rad)
    else:
        raise NotImplementedError("Type must be 'SMASH field' or 'cluster'.")

    table = download_data(data_name, info[0], info[1], rad)
    fname = settings["schema_name"] + '_' + info[2]  # still to improve...
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


def validate_radius(radius):
    """
    Validate and return the radius input.
    """
    if not isinstance(radius, (int, float)):
        raise TypeError("Radius must be a number.")
    if radius <= 0 or radius > 1.5:
        raise ValueError("Radius must be > 0 and <= 1.5 deg.")

    return radius


def get_smash_field(path, settings, radius):
    """
    Get RA, DEC, filename and message for a given SMASH field.
    """
    path = os.path.join(path, settings['tabs_path'], 'TAP-List-of-Fields.fits')
    fields = Table.read(path, format='fits')
    if int(settings['object']) not in fields['fieldid']:
        raise ValueError(f"Field {settings['object']} not available!")
    line = fields[fields['fieldid'] == settings['object']]

    id, ra, dec = line['fieldid'].item(), line['ra'].item(), line['dec'].item()
    fname = f"TAP_f{id}_{str(radius).replace('.','p')}deg"
    msg = f"Field {id} (RA {ra:.5f}, DEC {dec:.5f}), rad = {radius:.3f} deg?"

    return (ra, dec, fname, msg)


def get_cluster_coords(path, settings, radius):
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
    fname = f"{obj_id.replace(' ','')}_{str(radius).replace('.','p')}deg"
    msg = f"{obj_id} (RA {ra:.5f}, Dec {dec:.5f}), rad = {radius:.3f}?"

    return ra, dec, fname, msg


def download_data(db, RA, DEC, rad):
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
    adql = '''SELECT *
    FROM %s
        WHERE
            't'= Q3C_RADIAL_QUERY(ra,dec,%.5f,%.5f,%.3f)
    ''' % (db, RA, DEC, rad)
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
