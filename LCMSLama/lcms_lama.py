""""
Author: Olly Bayley

The aim of this package is to be a general point of entry to the LAMS package.
As of 12/02/2024 This is an incomplete placeholder while we wait for the platform to be ready and
the exact calling structure is established.
"""
import os
import time
import logging
import shutil
from LAMA.LCMSLama.lams_prescreen import LamsPrescreen
from LAMA.LCMSLama.lams_analysis import LamsAnalysis

PATH_TO_EXP = r'C:\Users\obayley\Platform_Data\Olly_Test\Test11'  # tmp hardcode
PATH_TO_DATA = os.path.join(PATH_TO_EXP, 'LCMS_data')  # tmp hardcode
PATH_TO_ANAL_JSON = os.path.join(PATH_TO_EXP, 'LCMS_analysis')  # tmp hardcode
prescreen_obj = LamsPrescreen(path_to_experiment=PATH_TO_EXP,
                              path_to_analysis_setup_json=PATH_TO_ANAL_JSON,
                              path_to_data=PATH_TO_DATA)
analysis_obj = LamsAnalysis(path_to_experiment=PATH_TO_EXP,
                            path_to_analysis_setup_json=PATH_TO_ANAL_JSON,
                            path_to_data=PATH_TO_DATA)


def main():
    # user input version
    while True:
        user_input = input("Enter command (calib/analyse/done): ")
        if user_input.lower() == 'analyse':
            print("Analysing...")
            analysis_obj.run_analysis()
        elif user_input.lower() == 'calib':
            print("Calibrating...")
            prescreen_obj.run_calibration()
            analysis_obj.prepare_analysis()
        elif user_input.lower() == 'done':
            break
        else:
            print("Invalid input. Please enter 'calibrate' or 'done'.")
        time.sleep(0.1)

    analysis_obj.report_all_runs()


if __name__ == '__main__':
    main()

#
# # automatic running
# temp_data_store_path = os.path.join(PATH_TO_EXP, "data_store")
#
# # Set the log file name and path
# log_file_name = "runtime_logfile.log"
# log_file_path = PATH_TO_EXP
#
# # Set up logging configuration
# logging.basicConfig(
#     filename=log_file_path,
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     filemode='a'  # 'w' = overwrite the logfile each run, 'a' = append each run to the logfile
# )
#
# start_time = time.time()
# prescreen_obj.run_calibration()
# analysis_obj.prepare_analysis()
# end_time = time.time()
# logging.info(f"Calibration completed in {round(end_time - start_time, 3)} seconds")
#
# count = 1
# for run_file in os.listdir(temp_data_store_path):
#     start_time = time.time()
#     source_file_path = os.path.join(temp_data_store_path, run_file)
#     destination_file_path = os.path.join(PATH_TO_DATA, run_file)
#     shutil.copy2(source_file_path, destination_file_path)
#     analysis_obj.run_analysis()
#     end_time = time.time()
#     logging.info(f"Run {count} analysis completed in {round(end_time - start_time, 3)} seconds")
#     count += 1
#     time.sleep(0.01)
