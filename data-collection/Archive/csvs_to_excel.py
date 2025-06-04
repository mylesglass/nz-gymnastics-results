import os
import pandas as pd
import re
from openpyxl.utils import get_column_letter, column_index_from_string

def sanitize_sheet_name(filename):
    """
    Sanitizes a filename to be a valid Excel sheet name.
    Excel sheet names must be 31 characters or less and cannot contain:
    * (asterisk)
    ? (question mark)
    : (colon)
    / (forward slash)
    \ (backslash)
    [ (left square bracket)
    ] (right square bracket)
    """
    # Remove the .csv extension
    name_without_extension = os.path.splitext(filename)[0]
    # Replace invalid characters with an underscore
    sanitized_name = re.sub(r'[\\/*?:\[\]]', '_', name_without_extension).rsplit(' - ', 1)[-1]
    
    # Truncate to 31 characters if necessary
    return sanitized_name[:31]

def set_col_width(worksheet, col, width):
    worksheet.column_dimensions[col].width = width

def set_col_decimal_place(df, worksheet, decimal_format_column_letter, decimal_format_string):
    try:
        # Ensure decimal_format_column_letter is valid and df has enough columns
        col_to_format_idx = column_index_from_string(decimal_format_column_letter.upper())

        if 1 <= col_to_format_idx <= df.shape[1]:
            print(f"   - Applying decimal format '{decimal_format_string}' to column '{decimal_format_column_letter.upper()}' in sheet")
            for row_idx in range(2, worksheet.max_row + 1): # Start from row 2 to skip header
                cell = worksheet[f"{decimal_format_column_letter.upper()}{row_idx}"]
                if isinstance(cell.value, (int, float)): # Check if it's a number
                    cell.number_format = decimal_format_string
            print(f"     ...done.")
        else:
            print(f"   - Warning: Column '{decimal_format_column_letter.upper()}' for decimal formatting is out of bounds for sheet (max cols: {df.shape[1]}).")
    except TypeError:
            print(f"   - Warning: Invalid column letter '{decimal_format_column_letter}' provided for decimal formatting.")


def csv_files_to_excel(input_directory, output_excel_file):
    """
    Reads all CSV files from a specified directory and writes each
    to a separate sheet in a single Excel file.

    Args:
        input_directory (str): The path to the directory containing CSV files.
        output_excel_file (str): The name (including .xlsx extension) 
                                 for the output Excel file.
    """
    try:
        # Check if the input directory exists
        if not os.path.isdir(input_directory):
            print(f"Error: Input directory '{input_directory}' not found.")
            return

        # Get a list of all CSV files in the directory
        csv_files = [f for f in os.listdir(input_directory) if f.endswith('.csv')]

        if not csv_files:
            print(f"No CSV files found in '{input_directory}'.")
            return

        # Create a Pandas Excel writer using openpyxl as the engine
        # The 'if_sheet_exists' parameter is available from pandas 1.4.0
        # For older versions, you might need to handle existing sheets differently
        # or ensure the output file doesn't exist.
        try:
            writer = pd.ExcelWriter(output_excel_file, engine='openpyxl')
        except Exception as e:
            print(f"Error creating Excel writer. Do you have 'openpyxl' installed? (pip install openpyxl)")
            print(f"Details: {e}")
            return
            
        print(f"Processing CSV files from: {input_directory}")

        # Loop through each CSV file
        for csv_file in csv_files:
            file_path = os.path.join(input_directory, csv_file)
            sheet_name = sanitize_sheet_name(csv_file)
            
            try:
                # Read the CSV file into a pandas DataFrame
                df = pd.read_csv(file_path)
                
                # Write the DataFrame to a new sheet in the Excel file
                # index=False means the DataFrame index will not be written to the Excel sheet
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"Successfully added '{csv_file}' as sheet '{sheet_name}'.")

                # --- Apply auto-filter using openpyxl ---
                # Get the workbook and the specific sheet
                workbook = writer.book
                worksheet = writer.sheets[sheet_name]

                # Add auto-filters to the header row
                if not df.empty: # Only add filters if there's data (and thus headers)
                    # worksheet.dimensions gives the range of all cells with data, e.g., A1:G50
                    worksheet.auto_filter.ref = worksheet.dimensions
                    print(f"   - Applied auto-filter to sheet '{sheet_name}'.")

                # Set width for column B
                # Check if the target column actually exists (i.e., DataFrame has at least that many columns)
                # For 'B', we need at least 2 columns (index 1)
                set_col_width(worksheet, "B", 18)
                set_col_width(worksheet, "C", 18)
                set_col_width(worksheet, "D", 12)
                set_col_width(worksheet, "H", 18)

                worksheet.column_dimensions["F"].hidden = True 
                worksheet.column_dimensions["H"].hidden = True 
                worksheet.column_dimensions["AE"].hidden = True 
            
                set_col_decimal_place(df, worksheet, "I", "0.000")
                set_col_decimal_place(df, worksheet, "K", "0.000")
                set_col_decimal_place(df, worksheet, "N", "0.000")
                set_col_decimal_place(df, worksheet, "P", "0.000")
                set_col_decimal_place(df, worksheet, "S", "0.000")
                set_col_decimal_place(df, worksheet, "U", "0.000")
                set_col_decimal_place(df, worksheet, "X", "0.000")
                set_col_decimal_place(df, worksheet, "Z", "0.000")
                set_col_decimal_place(df, worksheet, "AC", "0.000")

                set_col_decimal_place(df, worksheet, "J", "0.0")
                set_col_decimal_place(df, worksheet, "L", "0.0")
                set_col_decimal_place(df, worksheet, "O", "0.0")
                set_col_decimal_place(df, worksheet, "Q", "0.0")
                set_col_decimal_place(df, worksheet, "T", "0.0")
                set_col_decimal_place(df, worksheet, "V", "0.0")
                set_col_decimal_place(df, worksheet, "Y", "0.0")
                set_col_decimal_place(df, worksheet, "AA", "0.0")

                worksheet.freeze_panes = 'D2'
                

            except pd.errors.EmptyDataError:
                print(f"Warning: CSV file '{csv_file}' is empty. Creating an empty sheet '{sheet_name}'.")
                # Create an empty DataFrame and write it to keep the sheet
                empty_df = pd.DataFrame()
                empty_df.to_excel(writer, sheet_name=sheet_name, index=False)
            except Exception as e:
                print(f"Error processing file '{csv_file}': {e}")
                # Optionally, you could skip the file or handle the error differently

        # Save the Excel file
        try:
            writer.close() # Prior to pandas 1.3.0, use writer.save()
            print(f"\nExcel file '{output_excel_file}' created successfully!")
        except Exception as e: # For pandas < 1.3.0, writer.save() might be needed.
            print(f"Error saving Excel file: {e}")


    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # --- Configuration ---
    # IMPORTANT: Replace with the actual path to your CSV files directory
    # Example for Windows: "C:\\Users\\YourUser\\Documents\\CSV_Files"
    # Example for macOS/Linux: "/Users/youruser/Documents/CSV_Files"
    csv_directory = "C:\\Users\\myles\\Documents\\GitHub\\nz-gymnastics-results\\data-collection\\WAG\\Manawatu GymSports WAG Opens 2025" 
    
    # Name for the output Excel file
    excel_output_filename = "combined_csv_data.xlsx"
    # --- End Configuration ---

    # Ensure the output filename has the .xlsx extension
    if not excel_output_filename.endswith('.xlsx'):
        excel_output_filename += '.xlsx'
        
    # Construct the full path for the output file (optional, saves in script's directory by default)
    # If you want to save it in a specific location, provide the full path.
    # excel_output_path = os.path.join(csv_directory, excel_output_filename) # Saves in the CSV directory
    excel_output_path = excel_output_filename # Saves in the script's current directory

    if csv_directory == "path/to/your/csv_files":
        print("--------------------------------------------------------------------")
        print("IMPORTANT: Please update the 'csv_directory' variable in the script")
        print("           to point to the directory containing your CSV files.")
        print("--------------------------------------------------------------------")
    else:
        csv_files_to_excel(csv_directory, excel_output_path)
