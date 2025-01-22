import os
import csv

# Define the base directories
base_dir = '../../data/GRID_corpus_normal/original_transcriptions/'
output_base_dir = '../../data/GRID_corpus_normal/transcriptions/'


def create_output_dir_structure(base_dir, output_base_dir):
    """
    Create a mirrored directory structure for the output CSV files.
    """
    for root, dirs, _ in os.walk(base_dir):
        # Compute the corresponding output directory
        relative_path = os.path.relpath(root, base_dir)
        output_dir = os.path.join(output_base_dir, relative_path)
        os.makedirs(output_dir, exist_ok=True)


def convert_align_to_csv(align_file, csv_file):
    """
    Converts an .align file to a .csv file.
    """
    try:
        with open(align_file, 'r') as align, open(csv_file, 'w', newline='') as csv_output:
            csv_writer = csv.writer(csv_output)
            # csv_writer.writerow(['start_time', 'end_time', 'subtitle'])  # Write the header

            for line in align:
                parts = line.strip().split()
                if len(parts) == 3:  # Ensure valid format
                    start_time = int(parts[0])  # Convert start_time to integer
                    end_time = int(parts[1])  # Convert end_time to integer
                    subtitle = parts[2]
                    csv_writer.writerow([start_time, end_time, subtitle])
    except Exception as e:
        print(f"Error converting {align_file} to CSV: {e}")


def process_transcriptions(base_dir, output_base_dir):
    """
    Loops through all speaker folders and converts .align files to .csv.
    """
    create_output_dir_structure(base_dir, output_base_dir)

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.align'):
                align_file = os.path.join(root, file)

                # Compute the corresponding output CSV file path
                relative_path = os.path.relpath(root, base_dir)
                output_dir = os.path.join(output_base_dir, relative_path)
                csv_file = os.path.join(output_dir, os.path.splitext(file)[0] + '.csv')

                convert_align_to_csv(align_file, csv_file)


if __name__ == "__main__":
    process_transcriptions(base_dir, output_base_dir)
    print("All .align files have been converted to .csv format in 'csv_transcriptions/'.")
