from __future__ import print_function
import six

from collections import OrderedDict

from astropy.io import registry
from astropy.io import fits
from astropy.wcs import WCS
from astropy.nddata import StdDevUncertainty
import astropy.units as u
from warnings import warn

from .data_objects import CubeData, SpectrumData

fits_configs = OrderedDict()
fits_configs.update(
    {'default': {
        'flux': {
            'ext': 0,
            'required': True,
            'wcs': True,
        },
        'error': {
            'ext': 1,
        },
        'mask': {
            'ext': 2,
        },
    }}
)
fits_configs.update(
    {'MaNGA': {
        'flux': {
            'ext': 0,
            'ext_card': 'FLUXEXT',
            'required': True,
        },
        'error': {
            'ext': 0,
            'ext_card': 'ERREXT',
        },
        'mask': {
            'ext': 0,
            'ext_card': 'MASKEXT',
        },
    }}
)


def fits_cube_reader(filename, config=None):
    hdulist = fits.open(filename)
    data = None
    if config:
        data = cube_from_config(hdulist, fits_configs[config])
    else:
        for config in reversed(fits_configs):
            try:
                data = cube_from_config(hdulist, fits_configs[config])
                break
            except Exception:
                continue
    if not data:
        raise RuntimeError('Cannot find cube in fits file.')

    return data


def cube_from_config(hdulist, config):
    hdu_ids = dict()
    def hdu_by_type(ext_type):
        return hdulist[hdu_ids[ext_type]]

    for ext_type in config:
        params = config[ext_type]
        try:
            ext = params['ext']
            if 'ext_card' in params:
                ext = hdulist[ext].header[params['ext_card']]
            hdu_ids[ext_type] = ext
        except KeyError:
            if params.get('required'):
                raise RuntimeError(
                    'Required extension "{}" not found.'.format(ext_type)
                )

    try:
        flux_value = hdu_by_type('flux').data
        wcs_header = hdu_by_type('flux').header
        wcs = WCS(wcs_header)
    except KeyError:
        flux_value = None
        wcs_header = None
        wcs = None
    try:
        err_value = StdDevUncertainty(hdu_by_type('error').data)
    except KeyError:
        err_value = None
    try:
        mask_value = hdu_by_type('mask').data.astype(int)
    except KeyError:
        mask_value = None

    try:
        unit = u.Unit(hdu_by_type('flux').header['BUNIT'].split(' ')[-1])
    except (KeyError, ValueError):
        warn("Could not find 'BUNIT' in WCS header; assuming"
             "'erg/s/cm^2/Angstrom/voxel'")
        # TODO this is MaNGA-specific
        unit = u.Unit('erg/s/cm^2/Angstrom/voxel')

    data = CubeData(data=flux_value,
                    uncertainty=err_value,
                    mask=mask_value,
                    wcs=wcs,
                    unit=unit)
    data.meta['hdu_ids'] = hdu_ids.values()
    return data


def fits_spectrum_reader(filename):
    hdulist = fits.open(filename)
    header = hdulist[1].header

    try:
        unit = u.Unit(hdulist[1].header['CUNIT'].split(' ')[-1])
    except KeyError:
        warn("Could not find 'CUNIT' in WCS header; assuming 'Jy'")
        unit = u.Unit('Jy')

    return SpectrumData(data=hdulist[1].data[:, 25, 25],
                        uncertainty=StdDevUncertainty(
                            hdulist[2].data[:, 25, 25]
                        ),
                        mask=hdulist[3].data[:, 25, 25].astype(int),
                        wcs=WCS(header),
                        unit=unit)


def fits_identify(origin, *args, **kwargs):
    return isinstance(args[0], six.string_types) and \
           args[0].lower().split('.')[-1] in ['fits', 'fit']

try:
    registry.register_reader('fits', CubeData, fits_cube_reader)
    registry.register_reader('fits', SpectrumData, fits_spectrum_reader)
    registry.register_identifier('fits', CubeData, fits_identify)
    registry.register_identifier('fits', SpectrumData, fits_identify)
except Exception:
    warn('Items already exist in IO registry.')
