from pathlib import Path

import ipywidgets as ipw
from ccdproc import ImageFileCollection
from ipyautoui.custom import FileChooser

from stellarphot import PhotometryData
from stellarphot.settings import (
    PhotometryApertures,
    PhotometryFileSettings,
    ui_generator,
)
from stellarphot.settings.custom_widgets import Spinner

__all__ = ["TessAnalysisInputControls", "PhotometrySettingsOLDBAD"]


class TessAnalysisInputControls(ipw.VBox):
    """
    A class to hold the widgets for choosing TESS input
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hidden = ipw.Layout(display="none")

        self.phot_chooser = FileChooser(filter_pattern=["*.csv", "*.fits", "*.ecsv"])
        self._fits_openr = ipw.VBox(
            children=[
                ipw.HTML(value="<h3>Select your photometry/flux file</h3>"),
                self.phot_chooser,
            ]
        )
        self.tic_file_chooser = FileChooser(filter_pattern=["*.json"])
        fits_openr2 = ipw.VBox(
            children=[
                ipw.HTML(value="<h3>Select your TESS info file</h3>"),
                self.tic_file_chooser,
            ],
            layout=hidden,
        )
        self._passband = ipw.Dropdown(
            description="Ccoose Filter",
            options=["gp", "ip"],
            disabled=True,
            layout=hidden,
        )

        spinner = Spinner(message="<h4>Loading photometry...</h4>")

        self.phot_data = None

        def update_filter_list(_):
            spinner.start()
            self.phot_data = PhotometryData.read(self.phot_chooser.value)
            passband_data = self.phot_data["passband"]
            fits_openr2.layout.display = "flex"
            self._passband.layout.display = "flex"
            self._passband.options = sorted(set(passband_data))
            self._passband.disabled = False
            self._passband.value = self._passband.options[0]
            spinner.stop()

        self.phot_chooser.observe(update_filter_list, names="_value")
        self.children = [self._fits_openr, spinner, fits_openr2, self._passband]

    @property
    def tic_info_file(self):
        p = Path(self.tic_file_chooser.value)
        selected_file = p.name
        if not selected_file:
            raise ValueError("No TIC info json file selected")
        return p

    @property
    def photometry_data_file(self):
        p = Path(self.phot_chooser.value)
        selected_file = p.name
        if not selected_file:
            raise ValueError("No photometry data file selected")
        return p

    @property
    def passband(self):
        return self._passband.value


class PhotometrySettingsOLDBAD:
    """
    A class to hold the widgets for photometry settings.

    Attributes
    ----------

    aperture_locations : `pathlib.Path`
        This is the path to the file containing the aperture locations.

    box : `ipywidgets.VBox`
        This is a box containing the widgets.

    image_folder : `pathlib.Path`
        This is the path to the folder containing the images.

    ifc : `ccdproc.ImageFileCollection`
        The ImageFileCollection for the selected folder.

    object_name : str
        The name of the object.
    """

    def __init__(self):
        self._file_loc_widget = ui_generator(PhotometryFileSettings)
        self._object_name = ipw.Dropdown(
            description="Choose object", style=dict(description_width="initial")
        )

        self._file_loc_widget.observe(self._update_locations)
        self.ifc = None
        self._box = ipw.VBox()
        self._box.children = [self._file_loc_widget, self._object_name]

    @property
    def box(self):
        """
        The box containing the widgets.
        """
        return self._box

    @property
    def image_folder(self):
        """
        The path to the folder containing the images.
        """
        return self.file_locations.image_folder

    @property
    def aperture_locations(self):
        """
        The path to the file containing the aperture locations
        """
        return self.file_locations.aperture_locations_file

    @property
    def object_name(self):
        """
        The name of the object.
        """
        return self._object_name.value

    def _update_locations(self, change):
        self.file_locations = PhotometryFileSettings(**self._file_loc_widget.value)
        self._update_ifc(change)
        if Path(self.file_locations.aperture_settings_file).is_file():
            self._update_aperture_settings(change)

    def _update_ifc(self, change):
        self.ifc = ImageFileCollection(self.file_locations.image_folder)
        self._update_object_list(change)

    def _update_object_list(self, change):  # noqa: ARG002
        """
        Widget callbacks need to accept a single argument, even if it is not used.
        """
        if self.ifc.summary:
            self._object_name.options = sorted(
                set(self.ifc.summary["object"][~self.ifc.summary["object"].mask])
            )
        else:
            self._object_name.options = []

    def _update_aperture_settings(self, change):  # noqa: ARG002
        """
        Widget callbacks need to accept a single argument, even if it is not used.
        """
        self.aperture_settings = PhotometryApertures.parse_file(
            self.file_locations.aperture_settings_file
        )
