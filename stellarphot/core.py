import re

from astropy import units as u
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.table import Column, QTable, Table
from astropy.time import Time
from astropy.units import Quantity

from pydantic import BaseModel, root_validator

import numpy as np

__all__ = [
    "Camera",
    "BaseEnhancedTable",
    "PhotometryData",
    "CatalogData",
    "SourceListData",
]


# Approach to validation of units was inspired by the GammaPy project
# which did it before we did:
# https://docs.gammapy.org/dev/_modules/gammapy/analysis/config.html


class QuantityType(Quantity):
    # Validator for Quantity type
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        try:
            v = Quantity(v)
        except TypeError:
            raise ValueError(f"Invalid value for Quantity: {v}")
        else:
            if not v.unit.bases:
                raise ValueError("Must provided a unit")
        return v


class PixelScaleType(Quantity):
    # Validator for pixel scale type
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        try:
            v = Quantity(v)
        except TypeError:
            raise ValueError(f"Invalid value for Quantity: {v}")
        if (
            len(v.unit.bases) != 2
            or v.unit.bases[0].physical_type != "angle"
            or v.unit.bases[1].name != "pix"
        ):
            raise ValueError(f"Invalid unit for pixel scale: {v.unit!r}")
        return v


class Camera(BaseModel):
    """
    A class to represent a CCD-based camera.

    Parameters
    ----------

    gain : `astropy.quantity.Quantity`
        The gain of the camera in units such the product of `gain`
        times the image data has units equal to that of the `read_noise`.

    read_noise : `astropy.quantity.Quantity`
        The read noise of the camera with units.

    dark_current : `astropy.quantity.Quantity`
        The dark current of the camera in units such that, when multiplied by
        exposure time, the unit matches the units of the `read_noise`.

    pixel_scale : `astropy.quantity.Quantity`
        The pixel scale of the camera in units of arcseconds per pixel.

    Attributes
    ----------

    gain : `astropy.quantity.Quantity`
        The gain of the camera in units such the product of `gain`
        times the image data has units equal to that of the `read_noise`.

    read_noise : `astropy.quantity.Quantity`
        The read noise of the camera with units.

    dark_current : `astropy.quantity.Quantity`
        The dark current of the camera in units such that, when multiplied by
        exposure time, the unit matches the units of the `read_noise`.

    pixel_scale : `astropy.quantity.Quantity`
        The pixel scale of the camera in units of arcseconds per pixel.

    Notes
    -----
    The gain, read noise, and dark current are all assumed to be constant
    across the entire CCD.

    Examples
    --------
    >>> from astropy import units as u
    >>> from stellarphot import Camera
    >>> camera = Camera(gain=1.0 * u.electron / u.adu,
    ...                 read_noise=1.0 * u.electron,
    ...                 dark_current=0.01 * u.electron / u.second,
    ...                 pixel_scale=0.563 * u.arcsec / u.pixel)
    >>> camera.gain
    <Quantity 1. electron / adu>
    >>> camera.read_noise
    <Quantity 1. electron>
    >>> camera.dark_current
    <Quantity 0.01 electron / s>
    >>> camera.pixel_scale
    <Quantity 0.563 arcsec / pix>

    """

    gain: QuantityType
    read_noise: QuantityType
    dark_current: QuantityType
    pixel_scale: PixelScaleType

    class Config:
        validate_all = True
        validate_assignment = True
        extra = "forbid"
        json_encoders = {
            Quantity: lambda v: f"{v.value} {v.unit}",
            QuantityType: lambda v: f"{v.value} {v.unit}",
            PixelScaleType: lambda v: f"{v.value} {v.unit}",
        }

    # When the switch to pydantic v2 happens, this root_validator will need
    # to be replaced by a model_validator decorator.
    @root_validator(skip_on_failure=True)
    @classmethod
    def validate_gain(cls, values):
        # Get read noise units
        rn_unit = Quantity(values["read_noise"]).unit

        # Check that gain and read noise have compatible units, that is that
        # gain is read noise per adu.
        gain = values["gain"]
        if (
            len(gain.unit.bases) != 2
            or gain.unit.bases[0] != rn_unit
            or gain.unit.bases[1] != u.adu
        ):
            raise ValueError(
                f"Gain units {gain.unit} are not compatible with "
                f"read noise units {rn_unit}."
            )

        # Check that dark current and read noise have compatible units, that is
        # that dark current is read noise per second.
        dark_current = values["dark_current"]
        if (
            len(dark_current.unit.bases) != 2
            or dark_current.unit.bases[0] != rn_unit
            or dark_current.unit.bases[1] != u.s
        ):
            raise ValueError(
                f"Dark current units {dark_current.unit} are not "
                f"compatible with read noise units {rn_unit}."
            )

        # Dark current validates against read noise
        return values

    def copy(self):
        return Camera(
            gain=self.gain,
            read_noise=self.read_noise,
            dark_current=self.dark_current,
            pixel_scale=self.pixel_scale,
        )

    def __copy__(self):
        return self.copy()

    def __repr__(self):
        return (
            f"Camera(gain={self.gain}, read_noise={self.read_noise}, "
            f"dark_current={self.dark_current}, pixel_scale={self.pixel_scale})"
        )


class BaseEnhancedTable(QTable):
    """
    A class to validate an `astropy.table.QTable` table of astronomical data during
    creation and store metadata as attributes.

    This is based on the `astropy.timeseries.QTable` class. We extend this to
    allow for checking of the units for the columns to match the table_description,
    but what this returns is just an `astropy.table.QTable`.

    Parameters
    ----------

    input_data: `astropy.table.QTable` (Default: None)
        A table containing astronomical data of interest.  This table
        will be checked to make sure all columns listed in table_description
        exist and have the right units. Additional columns that
        may be present in data but are not listed in table_description will
        NOT be removed.  This data is copied, so any changes made during
        validation will not only affect the data attribute of the instance,
        the original input data is left unchanged.

    table_description: dict or dict-like (Default: None)
        This is a dictionary where each key is a required table column name
        and the value corresponding to each key is the required dtype
        (can be None).  This is used to check the format of the input data
        table.  Columns will be output in the order of the keys in the dictionary
        with any additional columns tacked on the end.

    colname_map: dict, optional (Default: None)
        A dictionary containing old column names as keys and new column
        names as values.  This is used to automatically update the column
        names to the desired names BEFORE the validation is performed.

    Notes
    -----

    This class is based on the `astropy.timeseries.QTable` class.  If no
    table_description and no input_data is provided, then an empty QTable
    is returned.  If table_description and input_data are provided, then
    validation of the inputs is performed and the resulting table is returned.
    """

    def __init__(
        self, *args, input_data=None, table_description=None, colname_map=None, **kwargs
    ):
        if (table_description is None) and (input_data is None):
            # Assume user is trying to create an empty table and let QTable
            # handle it
            super().__init__(*args, **kwargs)
        else:
            # Confirm a proper table description is passed (that is dict-like with keys
            # and values)
            try:
                self._table_description = {k: v for k, v in table_description.items()}
            except AttributeError:
                raise TypeError(
                    "You must provide a dict as table_description (input "
                    f"table_description is type {type(self._table_description)})."
                )

            # Check data before copying to avoid recusive loop and non-QTable
            # data input.
            if not isinstance(input_data, Table) or isinstance(
                input_data, BaseEnhancedTable
            ):
                raise TypeError(
                    "You must provide an astropy Table and NOT a "
                    "BaseEnhancedTable as input_data (currently of "
                    f"type {type(input_data)})."
                )

            # Copy data before potential modification
            data = input_data.copy()

            # Rename columns before validation (if needed)
            if colname_map is not None:
                # Confirm a proper colname_map is passed
                try:
                    self._colname_map = {k: v for k, v in colname_map.items()}
                except AttributeError:
                    raise TypeError(
                        "You must provide a dict as table_description "
                        "(input table_description is type "
                        f"{type(self._table_description)})."
                    )

                self._update_colnames(self._colname_map, data)

            # Validate the columns
            self._validate_columns(data)

            # Revise column order to be in the order listed in table_description
            # with unlisted columns tacked on the end
            order_col_list = list(self._table_description.keys())
            for col in data.colnames:
                if col not in order_col_list:
                    order_col_list.append(col)
            data = data[order_col_list]

            # Call QTable initializer to finish up
            super().__init__(data=data, **kwargs)

    def _validate_columns(self, data):
        # Check the format of the data table matches the table_description by
        # checking each column listed in table_description exists and is the
        # correct units.
        # NOTE: This ignores any columns not in the table_description, it
        # does not remove them.
        for this_col, this_unit in self._table_description.items():
            if this_unit is not None:
                # Check type
                try:
                    if data[this_col].unit != this_unit:
                        raise ValueError(
                            f"data['{this_col}'] is of wrong unit "
                            f"(should be {this_unit} but reported "
                            f"as {data[this_col].unit})."
                        )
                except KeyError:
                    raise ValueError(
                        f"data['{this_col}'] is missing from input " "data."
                    )
            else:  # Check that columns with no units but are required exist!
                try:
                    tempvar = data[this_col]
                except KeyError:
                    raise ValueError(
                        f"data['{this_col}'] is missing from input " "data."
                    )

    def _update_colnames(self, colname_map, data):
        # Change column names as desired, done before validating the columns,
        # which is why we work on _orig_data
        for orig_name, new_name in colname_map.items():
            try:
                data.rename_column(orig_name, new_name)
            except KeyError:
                raise ValueError(
                    f"data['{orig_name}'] is missing from input "
                    "data but listed in colname_map!"
                )

    def _update_passbands(self):
        # Converts filter names in filter column to AAVSO standard names
        # Assumes _passband_map is in namespace.
        for orig_pb, aavso_pb in self._passband_map.items():
            mask = self["passband"] == orig_pb
            self["passband"][mask] = aavso_pb

    def clean(self, remove_rows_with_mask=True, **other_restrictions):
        """
        Return a catalog with only the rows that meet the criteria specified.

        Parameters
        ----------

        catalog : `astropy.table.Table`
            Table of catalog information. There are no restrictions on the columns.

        remove_rows_with_mask : bool, optional
            If ``True``, remove rows in which one or more of the values is masked.

        other_restrictions: dict, optional
            Key/value pairs in which the key is the name of a column in the
            catalog and the value is the criteria that values in that column
            must satisfy to be kept in the cleaned catalog. The criteria must be
            simple, beginning with a comparison operator and including a value.
            See Examples below.

        Returns
        -------

        same type as object whose method was called
            Table with filtered data
        """
        comparisons = {
            '<': np.less,
            '=': np.equal,
            '>': np.greater,
            '<=': np.less_equal,
            '>=': np.greater_equal,
            '!=': np.not_equal
        }

        recognized_comparison_ops = '|'.join(comparisons.keys())
        keepers = np.ones([len(self)], dtype=bool)

        if remove_rows_with_mask and self.has_masked_values:
            for c in self.columns:
                keepers &= ~self[c].mask

        for column, restriction in other_restrictions.items():
            criteria_re = re.compile(r'({})([-+a-zA-Z0-9]+)'.format(recognized_comparison_ops))
            results = criteria_re.match(restriction)
            if not results:
                raise ValueError("Criteria {}{} not "
                                "understood.".format(column, restriction))
            comparison_func = comparisons[results.group(1)]
            comparison_value = results.group(2)
            new_keepers = comparison_func(self[column],
                                        float(comparison_value))
            keepers = keepers & new_keepers

        return self[keepers]


class PhotometryData(BaseEnhancedTable):
    """
    A modified `astropy.table.QTable` to hold reduced photometry data that
    provides the convience of validating the data table is in the proper
    format including units.  It returns an `PhotometryData` which is
    a `astropy.table.QTable` with additional attributes describing
    the observatory and camera.

    Parameters
    ----------

    input_data: `astropy.table.QTable`, optional (Default: None)
        A table containing all the instrumental aperture photometry results
        to be validated.  Note: It is allowed for the 'ra' and 'dec' columns
        to have np.nan values, but if they do, the 'bjd' column will not be
        computed and will also be left with 'np.nan'.

    observatory: `astropy.coordinates.EarthLocation`, optional (Default: None)
        The location of the observatory.

    camera: `stellarphot.Camera`, optional (Default: None)
        A description of the CCD used to perform the photometry.

    colname_map: dict, optional (Default: None)
        A dictionary containing old column names as keys and new column
        names as values.  This is used to automatically update the column
        names to the desired names before the validation is performed.

    passband_map: dict, optional (Default: None)
        A dictionary containing instrumental passband names as keys and
        AAVSO passband names as values. This is used to automatically
        update the passband column to AAVSO standard names if desired.

    retain_user_computed: bool, optional (Default: False)
        If True, any computed columns (see USAGE NOTES below) that already
        exist in `data` will be retained.  If False, will throw an error
        if any computed columns already exist in `data`.

    Attributes
    ----------
    camera: `stellarphot.Camera`
        A description of the CCD used to perform the photometry.

    observatory: `astropy.coordinates.EarthLocation`
        The location of the observatory.

    Notes
    -----
    For validation of inputs, you must provide camera, observatory, AND input_data,
    if you do not, an empty table will be returned.

    To be accepted as valid, the  `input_data` must MUST contain the following columns
    with the following units.  The data in those columns is NOT validated, the values in
    those columns could be invalid.  Furthermore, the 'consistent count units' below
    simply means it can be any unit, but it must be the same for all the columns with
    'consistent count units'.

    name                  unit
    -----------------     -------
    star_id               None
    RA                    u.deg
    Dec                   u.deg
    xcenter               u.pix
    ycenter               u.pix
    fwhm_x                u.pix
    fwhm_y                u.pix
    width                 u.pix
    aperture              u.pix
    aperture_area         u.pix
    annulus_inner         u.pix
    annulus_outer         u.pix
    annulus_area          u.pix
    aperture_sum          consistent count units
    annulus_sum           consistent count units
    sky_per_pix_avg       consistent count units (per pixel)
    sky_per_pix_med       consistent count units (per pixel)
    sky_per_pix_std       consistent count units (per pixel)
    aperture_net_cnts     consistent count units
    noise_cnts            consistent count units
    noise_electrons       u.electron
    snr                   None
    mag_inst              None
    mag_error             None
    exposure              u.s
    date-obs              astropy.time.Time with scale='utc'
    airmass               None
    passband              None
    file                  None

    In addition to these required columns, the following columns are created based
    on the input data during creation.

    bjd    (only if ra and dec are all real numbers, otherwise set to np.nan)
    night

    If these computed columns already exist in `data` class the class
    will throw an error a ValueError UNLESS`ignore_computed=True`
    is passed to the initializer, in which case the columns will be
    retained and not replaced with the computed values.
    """

    # Define columns that must be in table and provide information about their type, and
    # units.
    phot_descript = {
        "star_id": None,
        "ra": u.deg,
        "dec": u.deg,
        "xcenter": u.pix,
        "ycenter": u.pix,
        "fwhm_x": u.pix,
        "fwhm_y": u.pix,
        "width": u.pix,
        "aperture": u.pix,
        "aperture_area": u.pix,
        "annulus_inner": u.pix,
        "annulus_outer": u.pix,
        "annulus_area": u.pix,
        "aperture_sum": None,
        "annulus_sum": None,
        "sky_per_pix_avg": None,
        "sky_per_pix_med": None,
        "sky_per_pix_std": None,
        "aperture_net_cnts": None,
        "noise_cnts": None,
        "noise_electrons": u.electron,
        "snr": None,
        "mag_inst": None,
        "mag_error": None,
        "exposure": u.second,
        "date-obs": None,
        "airmass": None,
        "passband": None,
        "file": None,
    }
    observatory = None
    camera = None

    def __init__(
        self,
        *args,
        input_data=None,
        observatory=None,
        camera=None,
        colname_map=None,
        passband_map=None,
        retain_user_computed=False,
        **kwargs,
    ):
        if (observatory is None) and (camera is None) and (input_data is None):
            super().__init__(*args, **kwargs)
        else:
            # Perform input validation
            if not isinstance(observatory, EarthLocation):
                raise TypeError(
                    "observatory must be an "
                    "astropy.coordinates.EarthLocation object instead "
                    f"of type {type(observatory)}."
                )
            if not isinstance(camera, Camera):
                raise TypeError(
                    "camera must be a stellarphot.Camera object instead "
                    f"of type {type(camera)}."
                )

            # Check the time column is correct format and scale
            try:
                if input_data["date-obs"][0].scale != "utc":
                    raise ValueError(
                        "input_data['date-obs'] astropy.time.Time must "
                        "have scale='utc', "
                        f"not '{input_data['date-obs'][0].scale}'."
                    )
            except AttributeError:
                # Happens if first item dosn't have a "scale"
                raise ValueError(
                    "input_data['date-obs'] isn't column of "
                    "astropy.time.Time entries."
                )

            # Convert input data to QTable (while also checking for required columns)
            super().__init__(
                input_data=input_data,
                table_description=self.phot_descript,
                colname_map=colname_map,
                **kwargs,
            )

            # Add the TableAttributes directly to meta (and adding attribute
            # functions below) since using TableAttributes results in a
            # inability to access the values to due a
            # AttributeError: 'TableAttribute' object has no attribute 'name'
            self.meta["lat"] = observatory.lat
            self.meta["lon"] = observatory.lon
            self.meta["height"] = observatory.height
            self.meta["gain"] = camera.gain
            self.meta["read_noise"] = camera.read_noise
            self.meta["dark_current"] = camera.dark_current
            self.meta["pixel_scale"] = camera.pixel_scale

            # Check for consistency of counts-related columns
            counts_columns = [
                "aperture_sum",
                "annulus_sum",
                "aperture_net_cnts",
                "noise_cnts",
            ]
            counts_per_pixel_columns = [
                "sky_per_pix_avg",
                "sky_per_pix_med",
                "sky_per_pix_std",
            ]
            cnts_unit = self[counts_columns[0]].unit
            for this_col in counts_columns[1:]:
                if input_data[this_col].unit != cnts_unit:
                    raise ValueError(
                        f"input_data['{this_col}'] has inconsistent units "
                        f"with input_data['{counts_columns[0]}'] (should "
                        f"be {cnts_unit} but it's "
                        f"{input_data[this_col].unit})."
                    )
            for this_col in counts_per_pixel_columns:
                if cnts_unit is None:
                    perpixel = u.pixel**-1
                else:
                    perpixel = cnts_unit * u.pixel**-1
                if input_data[this_col].unit != perpixel:
                    raise ValueError(
                        f"input_data['{this_col}'] has inconsistent units "
                        f"with input_data['{counts_columns[0]}'] (should "
                        f"be {perpixel} but it's "
                        f"{input_data[this_col].unit})."
                    )

            # Compute additional columns (not done yet)
            computed_columns = ["bjd", "night"]

            # Check if columns exist already, if they do and retain_user_computed is
            # False,  throw an error.
            for this_col in computed_columns:
                if this_col in self.colnames:
                    if not retain_user_computed:
                        raise ValueError(
                            f"Computed column '{this_col}' already exist "
                            "in data. If you want to keep them, set "
                            "retain_user_computed=True."
                        )
                else:
                    # Compute the columns that need to be computed (match requries
                    # python>=3.10)
                    match this_col:
                        case "bjd":
                            self["bjd"] = self.add_bjd_col(observatory)

                        case "night":
                            # Generate integer counter for nights. This should be
                            # approximately the MJD at noon local before the evening of
                            # the observation.
                            hr_offset = int(observatory.lon.value / 15)
                            # Compute offset to 12pm Local Time before evening
                            LocalTime = Time(self["date-obs"]) + hr_offset * u.hr
                            hr = LocalTime.ymdhms.hour
                            # Compute number of hours to shift to arrive at 12 noon
                            # local time
                            shift_hr = hr.copy()
                            shift_hr[hr < 12] = shift_hr[hr < 12] + 12
                            shift_hr[hr >= 12] = shift_hr[hr >= 12] - 12
                            delta = (
                                -shift_hr * u.hr
                                - LocalTime.ymdhms.minute * u.min
                                - LocalTime.ymdhms.second * u.s
                            )
                            shift = Column(data=delta, name="shift")
                            # Compute MJD at local noon before the evening of this
                            # observation.
                            self["night"] = Column(
                                data=np.array(
                                    (Time(self["date-obs"]) + shift).to_value("mjd"),
                                    dtype=int,
                                ),
                                name="night",
                            )

                        case _:
                            raise ValueError(
                                f"Trying to compute column ({this_col}). "
                                "This should never happen."
                            )

            # Apply the filter/passband name update
            if passband_map is not None:
                self._passband_map = passband_map.copy()
                self._update_passbands()

    def add_bjd_col(self, observatory):
        """
        Returns a astropy column of barycentric Julian date times corresponding to
        the input observations.  It modifies that table in place.
        """

        if np.isnan(self["ra"]).any() or np.isnan(self["dec"]).any():
            print(
                "WARNING: BJD could not be computed in output PhotometryData object "
                "because some RA or Dec values are missing."
            )
            return np.full(len(self), np.nan)
        else:
            # Convert times at start of each observation to TDB (Barycentric Dynamical
            # Time)
            times = Time(self["date-obs"])
            times_tdb = times.tdb
            times_tdb.format = "jd"  # Switch to JD format

            # Compute light travel time corrections
            ip_peg = SkyCoord(ra=self["ra"], dec=self["dec"], unit="degree")
            ltt_bary = times.light_travel_time(ip_peg, location=observatory)
            time_barycenter = times_tdb + ltt_bary

            # Return BJD at midpoint of exposure at each location
            return Time(time_barycenter + self["exposure"] / 2, scale="tdb")

    @property
    def camera(self):
        return Camera(
            gain=self.meta["gain"],
            read_noise=self.meta["read_noise"],
            dark_current=self.meta["dark_current"],
            pixel_scale=self.meta["pixel_scale"],
        )

    @property
    def observatory(self):
        return EarthLocation(
            lat=self.meta["lat"], lon=self.meta["lon"], height=self.meta["height"]
        )


class CatalogData(BaseEnhancedTable):
    """
    A class to hold astronomical catalog data while performing validation
    to confirm the minumum required columns ('id', 'ra', 'dec', 'mag', and
    'passband') are present and have the correct units.

    As a convience function, when the user passes in an astropy table to validate,
    the user can also pass in a col_rename dict which can be used to rename columns
    in the data table BEFORE the check that the required columns are present.

    Parameters
    ----------
    input_data: `astropy.table.Table`, optional (Default: None)
        A table containing all the astronomical catalog data to be validated.
        This data is copied, so any changes made during validation will not
        affect the input data, only the data in the class.

    catalog_name: str, optional (Default: None)
        User readable name for the catalog.

    catalog_source: str, optional (Default: None)
        User readable designation for the source of the catalog (could be a
        URL or a journal reference).

    colname_map: dict, optional (Default: None)
        A dictionary containing old column names as keys and new column
        names as values.  This is used to automatically update the column
        names to the desired names BEFORE the validation is performed.

    passband_map: dict, optional (Default: None)
        A dictionary containing instrumental passband names as keys and
        AAVSO passband names as values. This is used to automatically
        update the passband column to AAVSO standard names if desired.

    Attributes
    ----------
    catalog_name: str
        User readable name for the catalog.

    catalog_source: str
        User readable designation for the source of the catalog (could be a
        URL or a journal reference).

    Notes
    -----
    For validation of inputs, you must provide input_data, catalog_name, and
    catalog_source.  If you do not, an empty table will be returned.

    input_data MUST contain the following columns with the following units:

    name                  unit
    -----------------     -------
    id                    None
    ra                    u.deg
    dec                   u.deg
    mag                   None
    passband              None
    """

    # Define columns that must be in table and provide information about their type, and
    # units.
    catalog_descript = {
        "id": None,
        "ra": u.deg,
        "dec": u.deg,
        "mag": None,
        "passband": None,
    }
    catalog_name = None
    catalog_source = None

    def __init__(
        self,
        *args,
        input_data=None,
        catalog_name=None,
        catalog_source=None,
        colname_map=None,
        passband_map=None,
        **kwargs,
    ):
        if (input_data is None) and (catalog_name is None) and (catalog_source is None):
            super().__init__(*args, **kwargs)
        else:
            self._passband_map = passband_map

            if input_data is not None:
                # Convert input data to QTable (while also checking for required
                # columns)
                super().__init__(
                    table_description=self.catalog_descript,
                    input_data=input_data,
                    colname_map=colname_map,
                    **kwargs,
                )
                # Add the TableAttributes directly to meta (and adding attribute
                # functions below) since using TableAttributes results in a
                # inability to access the values to due a
                # AttributeError: 'TableAttribute' object has no attribute 'name'
                self.meta["catalog_name"] = str(catalog_name)
                self.meta["catalog_source"] = str(catalog_source)

                # Apply the filter/passband name update
                if passband_map is not None:
                    self._passband_map = passband_map.copy()
                    self._update_passbands()

            else:
                raise ValueError("You must provide input_data to CatalogData.")

    @property
    def catalog_name(self):
        return self.meta["catalog_name"]

    @property
    def catalog_source(self):
        return self.meta["catalog_source"]


class SourceListData(BaseEnhancedTable):
    """
    A class to hold information on the source lists to pass to
    aperture photometry routines.  It verifies either image-based
    locations (x/y) or sky-based locations (ra/dec) exist.

    Parameters
    ----------
    input_data: `astropy.table.Table`, optional (Default: None)
        A table containing all the source list data to be validated.
        This data is copied, so any changes made during validation will not
        affect the input data, only the data in the class.

    colname_map: dict, optional (Default: None)
        A dictionary containing old column names as keys and new column
        names as values.  This is used to automatically update the column
        names to the desired names BEFORE the validation is performed.

    Attributes
    ----------
    has_ra_dec: bool
        True if the table has sky-based locations (ra/dec), False otherwise.

    has_x_y: bool
        True if the table has image-based locations (x/y), False otherwise.

    Notes
    -----
    For validation of inputs, you must provide input_data, if you do not,
    an empty table will be returned.

    input_data MUST contain the following columns in the following column:

    name                  unit
    -----------------     -------
    star_id               None

    In addition to the star_id columns you must have EITHER

    name                  unit
    -----------------     -------
    ra                    u.deg
    dec                   u.deg

    and/or

    name                  unit
    -----------------     -------
    xcenter               u.pix
    ycenter               u.pix

    to define the locations of the sources.  If one locaton pair is provided but not
    the other, the missing columns will be added but assigned NaN values.  It is ok
    to provide both sky and image location, but no validation is done to ensure they
    are consistent.
    """

    # Define columns that must be in table and provide information about their type, and
    # units.
    sourcelist_descript = {
        "star_id": None,
        "ra": u.deg,
        "dec": u.deg,
        "xcenter": u.pix,
        "ycenter": u.pix,
    }

    def __init__(self, *args, input_data=None, colname_map=None, **kwargs):
        if input_data is None:
            super().__init__(*args, **kwargs)
        else:
            # Check data before copying to avoid recusive loop and non-QTable
            # data input.
            if not isinstance(input_data, Table) or isinstance(
                input_data, BaseEnhancedTable
            ):
                raise TypeError(
                    "input_data must be an astropy Table (and not a "
                    "BaseEnhancedTable) as data."
                )

            # Process inputs and save as needed
            data = input_data.copy()

            # Rename columns before checking for ra/dec or xcenter/ycenter
            # columns being missing.
            if colname_map is not None:
                # Confirm a proper colname_map is passed
                try:
                    self._colname_map = {k: v for k, v in colname_map.items()}
                except AttributeError:
                    raise TypeError(
                        "You must provide a dict as table_description (it "
                        f"is type {type(self._colname_map)})."
                    )
                self._update_colnames(self._colname_map, data)

                # No need to repeat this
                self._colname_map = None
            else:
                self._colname_map = None

            # Check if RA/Dec or xcenter/ycenter are missing
            ra_dec_present = True
            x_y_present = True
            nosky_pos = (
                "ra" not in data.colnames
                or "dec" not in data.colnames
                or np.isnan(data["ra"].value).all()
                or np.isnan(data["dec"].value).all()
            )
            noimg_pos = (
                "xcenter" not in data.colnames
                or "ycenter" not in data.colnames
                or np.isnan(data["xcenter"].value).all()
                or np.isnan(data["ycenter"].value).all()
            )

            if nosky_pos:
                ra_dec_present = False
            if noimg_pos:
                x_y_present = False

            if nosky_pos and noimg_pos:
                raise ValueError(
                    "data must have either sky (ra, dec) or "
                    + "image (xcenter, ycenter) position."
                )

            # Create empty versions of any missing columns
            for this_col in ["ra", "dec", "xcenter", "ycenter"]:
                # Create blank ra/dec columns
                if this_col not in data.colnames:
                    data[this_col] = Column(
                        data=np.full(len(data), np.nan),
                        name=this_col,
                        unit=self.sourcelist_descript[this_col],
                    )

            # Convert input data to QTable (while also checking for required columns)
            super().__init__(
                table_description=self.sourcelist_descript,
                input_data=data,
                colname_map=None,
                **kwargs,
            )
            self.meta["has_ra_dec"] = ra_dec_present
            self.meta["has_x_y"] = x_y_present

    @property
    def has_ra_dec(self):
        return self.meta["has_ra_dec"]

    @property
    def has_x_y(self):
        return self.meta["has_x_y"]

    def drop_ra_dec(self):
        # drop sky-based positions from existing SourceListData structure
        self.meta["has_ra_dec"] = False
        self["ra"] = Column(data=np.full(len(self), np.nan), name="ra", unit=u.deg)
        self["dec"] = Column(data=np.full(len(self), np.nan), name="dec", unit=u.deg)

    def drop_x_y(self):
        # drop image-based positionsfrom existing SourceListData structure
        self.meta["has_x_y"] = False
        self["xcenter"] = Column(data=np.full(len(self), np.nan), name="ra", unit=u.deg)
        self["ycenter"] = Column(
            data=np.full(len(self), np.nan), name="dec", unit=u.deg
        )
