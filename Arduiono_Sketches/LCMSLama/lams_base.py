"""
Author: Olly Bayley
Created: 08/11/2023

This package serves as a base class for the LAMSPrescreen and LAMSAnalysis classes.
The base class useage allows better maintainability by reducing code and data storeage duplication
in the Prescreen and Analysis object code.

Note:
1)There are currently restrictions in the file naming. Due to the sorting in the 'load_lcms_data'
method. The file names should follow: "*Anything*_sample_#NUMBER#.ext". The 'sample' tag can be
changed the 'self.reaction_sample_tag'. The filename should finish with the run number followed
by the file extension
"""
# --- Imports ---
import os
import json
from glob import glob
import script_utilities as util
from LAMA.LCMSLama.user_interaction.user_objects import Gradient, InternalStandard
from LAMA.LCMSLama.user_interaction.settings import Settings


class LamsBase:
    """General base class containing universal methods and variables for the LAMS objects"""
    def __init__(
            self, path_to_experiment, path_to_analysis_setup_json=None, path_to_data=None
    ):
        # Default folder and file tags
        self.gradient_bkg_file_tag = "gradient"
        self.reaction_sample_tag = "sample"
        self.dad_data_folder_name = "LCMS_data"
        self.report_folder_name = "LCMS_analysis"
        self.analysis_json_filename = "analysis_setup.json"

        # Can initialise without giving the .json path but relies on expected dir structure
        if path_to_analysis_setup_json is None:
            path_to_analysis_setup_json = os.path.join(
                path_to_experiment, self.report_folder_name, self.analysis_json_filename
            )

        # Can initialise without giving the data path but relies on expected dir structure
        if path_to_data is None:
            path_to_data = os.path.join(path_to_experiment, self.dad_data_folder_name)

        # Passed global variables
        self.path_to_experiment = path_to_experiment
        self.path_to_setup = path_to_analysis_setup_json
        self.lcms_data_path = path_to_data

        # Other global variables
        self.chromatogram_analysis_parameters = None
        self.input_compounds_info = None
        self.lcms_exp_run_data = None
        self.gradient_bkg = None
        self.internal_standard_added = None
        self.analysis_settings = None

    @util.time_method
    def load_setup_data(self):
        """
        Adds the analysis settings in the analysis_setup.json to the LAMSAnalysis object
        """
        try:
            with open(
                    os.path.join(self.path_to_setup, self.analysis_json_filename),
                    mode='r',
                    encoding='utf-8'
            ) as infile:
                analysis_setup_data = json.load(infile)
                self.input_compounds_info = analysis_setup_data.get(
                    "prescreen_compound_info", {}
                )
                self.chromatogram_analysis_parameters = analysis_setup_data.get(
                    "chromatogram_analysis_parameters", {}
                )

        except FileNotFoundError as error:
            util.handle_error(f"File not found: {error}", error)
        except PermissionError as error:
            util.handle_error(f"Permission error: {error}", error)
        except json.JSONDecodeError as error:
            util.handle_error(f"JSON decode error: {error}", error)

    @util.time_method
    def load_lcms_data(self):
        """
        Finds the LCMS data, sorts it, and then adds to the run files to the LAMSPrescreen object
        Each instrument/software exports different file types so need to filter accordingly.
        """

        try:
            if not os.path.exists(self.lcms_data_path):
                os.makedirs(self.lcms_data_path)

            instrument = str(self.chromatogram_analysis_parameters.get("instrument"))
            if instrument == "chemstation":
                lcms_data = glob(self.lcms_data_path + "/*" + ".D")
                lcms_data = sorted(lcms_data)
            elif instrument == "openlab":
                lcms_data = glob(self.lcms_data_path + "/*" + ".sirslt")
                lcms_data = sorted(lcms_data)
            elif instrument == "labsolutions":
                lcms_data = glob(self.lcms_data_path + "/*" + ".txt")
                lcms_data = sorted(
                    lcms_data, key=lambda x: int(x.split("_")[-1][:-4])
                )  # See Note Below
            else:
                raise TypeError("Instrument type not recognised.\n")

            if not lcms_data:
                raise ValueError(
                    f"No experiment runs found in: {self.lcms_data_path} .\n"
                )

            self.lcms_exp_run_data = lcms_data

        except OSError as error:
            util.handle_error(f"Error making the new directory: {error}", error)
        except TypeError as error:
            util.handle_error(f"Type error: {error}", error)
        except ValueError as error:
            util.handle_error(f"Value error: {error}", error)
        except IndexError as error:
            util.handle_error(f"Index error: {error}", error)
        except AttributeError as error:
            util.handle_error(f"Attribute error: {error}", error)

        # Sorting relies on filenames following: '*Any*_samplename_number.txt'. Sorting fails if:
        # 1) The last part of the filename before the extension is not a number
        # 2) The file extension is not exactly four characters long (including the period) [:-4]
        # 3) There are non-numeric characters in the final section being converted to an integer

    @util.time_method
    def init_bkg_obj(self):
        """
        Initialise the Gradient object used as the background measurement and add to the
        LAMSPrescreen object
        """
        try:
            self.gradient_bkg = Gradient(
                next(
                    exp_run
                    for exp_run in self.lcms_exp_run_data
                    if self.gradient_bkg_file_tag in exp_run
                )
            )
        except RuntimeError as error:
            util.handle_error(f"Gradient background initialisation failed: {error}", error)
        except Exception as error:
            util.handle_error(f"Gradient background initialisation failed: {error}")

    @util.time_method
    def init_istd_obj(self):
        """
        Initialise the InternalStandard object (if used) and add to the LAMSPrescreen object
        """
        if self.chromatogram_analysis_parameters.get("internal_standard_name"):
            try:
                internal_standard_name = self.chromatogram_analysis_parameters.get(
                    "internal_standard_name"
                )
                internal_standard_conc = self.chromatogram_analysis_parameters.get(
                    "internal_standard_conc"
                )
                self.internal_standard_added = InternalStandard(
                    internal_standard_name, internal_standard_conc
                )
            except RuntimeError as error:
                util.handle_error(f"internal standard initialisation failed: {error}", error)
            except Exception as error:
                util.handle_error(f"internal standard initialisation failed: {error}")

    @util.time_method
    def set_analysis_settings(self):
        """
        Sets the campaign analysis settings based on the setting read from the analysis.json
        """
        try:
            anal_param = self.chromatogram_analysis_parameters
            self.analysis_settings = Settings(
                hplc_system_tag=str(anal_param.get("instrument")),
                detector_limit=float(anal_param.get("detector_limit")),
                absorbance_threshold=float(anal_param.get("absorbance_threshold")),
                wl_high_pass=float(anal_param.get("wl_high_pass")),
                wl_low_pass=float(anal_param.get("wl_low_pass")),
                peaks_high_pass=float(anal_param.get("peaks_high_pass")),
                peaks_low_pass=float(anal_param.get("peaks_low_pass")),
                spectrum_correl_thresh=float(anal_param.get("spectrum_correl_thresh")),
                relative_distance_thresh=float(anal_param.get("relative_distance_thresh")),
            )
        except Exception as error:
            util.handle_error(f"Failed to set analysis settings: {error}")
