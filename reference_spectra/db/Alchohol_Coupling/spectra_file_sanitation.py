def clean_csv_tabs_to_commas(input_path, output_path=None):
    """
    Reads a CSV-like text file, replaces tab characters with ', ',
    and writes the cleaned data back to a file.

    :param input_path: Path to the original file
    :param output_path: Path to save the cleaned file (if None, overwrites original)
    """
    # Read the file contents
    with open(input_path, 'r', encoding='utf-8') as f:
        data = f.read()

    # Replace tabs with comma+space
    clean_data = data.replace("\t", ", ")

    # Determine output path
    if output_path is None:
        output_path = input_path  # overwrite original

    # Save cleaned data
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(clean_data)

    print(f"Cleaned file saved to: {output_path}")

# Example usage:
# clean_csv_tabs_to_commas("raw_absorbance.csv", "cleaned_absorbance.csv")
