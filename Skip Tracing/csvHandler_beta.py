import os
import csv
import re

# Path to the CSV file
output_file_path = 'arcGIS_cape2.csv'

headers = [
    'Mailing Address',
    'Address',
    'City',
    'State',
    'Zipcode',
    'First Name',
    'Last Name',
    'Phone 1',
    'Phone Type 1',
    'Phone 2',
    'Phone Type 2',
    'Phone 3',
    'Phone Type 3',
    'Phone 4',
    'Phone Type 4',
    'Phone 5',
    'Phone Type 5',
    'Email',
    'Email 2',
    'Email 3',
    'Relative First Name',
    'Relative Last Name',
    'Relative Phone 1',
    'Relative Phone Type 1',
    'Relative Phone 2',
    'Relative Phone Type 2',
    'Relative Phone 3',
    'Relative Phone Type 3',
    'Relative Email 1',
    'Relative Email 2',
    'Relative Email 3'
]

# Function to initialize the CSV file with headers
def initialize_csv():
    """Initialize the CSV file with headers if it does not exist."""
    if not os.path.exists(output_file_path):
        with open(output_file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
        print('CSV file initialized with headers.')
    else:
        print('CSV file already exists. Skipping initialization.')

def strip_html_tags(text):
    """Remove HTML tags from the provided text."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def append_to_csv(data_to_write, output_file_path):
    """Append structured data to a CSV file."""
    if isinstance(data_to_write, dict):
        data = [
            data_to_write.get('Mailing Address', ''),
            data_to_write.get('Subject Property', ''),
            data_to_write.get('City', ''),
            data_to_write.get('State', ''),
            data_to_write.get('Zipcode', ''),
            data_to_write.get('First Name', ''),
            data_to_write.get('Last Name', ''),
            data_to_write.get('Phone 1', ''),
            data_to_write.get('Phone Type 1', ''),
            data_to_write.get('Phone 2', ''),
            data_to_write.get('Phone Type 2', ''),
            data_to_write.get('Phone 3', ''),
            data_to_write.get('Phone Type 3', ''),
            data_to_write.get('Phone 4', ''),
            data_to_write.get('Phone Type 4', ''),
            data_to_write.get('Phone 5', ''),
            data_to_write.get('Phone Type 5', ''),
            strip_html_tags(data_to_write.get('Email', '')),
            strip_html_tags(data_to_write.get('Email 2', '')),
            strip_html_tags(data_to_write.get('Email 3', '')),
            data_to_write.get('Relative First Name', ''),
            data_to_write.get('Relative Last Name', ''),
            data_to_write.get('Relative Phone 1', ''),
            data_to_write.get('Relative Phone Type 1', ''),
            data_to_write.get('Relative Phone 2', ''),
            data_to_write.get('Relative Phone Type 2', ''),
            data_to_write.get('Relative Phone 3', ''),
            data_to_write.get('Relative Phone Type 3', ''),
            strip_html_tags(data_to_write.get('Relative Email 1', '')),
            strip_html_tags(data_to_write.get('Relative Email 2', '')),
            strip_html_tags(data_to_write.get('Relative Email 3', ''))
        ]
    else:
        print(f"Error: data_to_write is not a dictionary, it is {type(data_to_write)}")
        return

    try:
        with open(output_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(data)
    except Exception as e:
        print(f"Error appending data to CSV: {e}")
