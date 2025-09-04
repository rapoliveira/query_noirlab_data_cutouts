# Query NOIRLab database: catalogs and image cutouts

This repository contains tools for querying the **NOIRLab Data Lab** (e.g., SMASH DR2, Gaia EDR3) and retrieving the catalogs and image cutouts around sky coordinates.
The query is done with the `service.search()` method from the `pyvo` library, using an ADQL format to make a cone search.

## Features

- Query NOIRLab databases (e.g., `smash_dr2.object`, `smash_dr2.exposure`).
- Retrieve metadata and catalogs for selected objects.
- Download image cutouts centered on RA/Dec with configurable size.

A YAML file is used to define the input parameters.
At the moment, it is only possible to download an entire [SMASH field](https://github.com/rapoliveira/query_noirlab_data_cutouts/blob/main/tables/TAP-List-of-Fields.fits) (numbered from 1 to 247) or input the name of a cluster listed in Bica catalogues.
Support for using coordinates (or a file with multiple coordinates) and for searching any cluster through Vizier will be added soon.


## Installation and usage

Clone the repository and install requirements:

```bash
git clone https://github.com/your-username/query_noirlab_data_cutouts.git
cd query_noirlab_data_cutouts
pip install -r requirements.txt
python3 query_noirlab.py query_settings.yaml
```

As it is, the YAML file will download data from the `smash_dr2.object`, using the service.search method (the only method working so far), for the cluster HW77, with a radius of 5 arcmin.

## Example figures: CMD and cutout image

No figures are saved yet, but below there is an example of CMD and cutout image to be implemented in this code.

<table>
  <tr>
    <td><img src="figures/example_cmd.png" alt="CMD 1" width="300"></td>
    <td><img src="figures/example_cutout.png" alt="Cutout" width="300"></td>
  </tr>
  <tr>
    <td align="center"><sub>Example of a CMD downloaded for the cluster NGC152.</sub></td>
    <td align="center"><sub>Example of an image cutout for the cluster L110.</sub></td>
  </tr>
</table>


Last updated: 04 Sep 2025
