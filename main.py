import yaml
import csv
from io import StringIO
# import yaml.resolver
# import re

INPUT_DIR = '.\\input\\'
OUTPUT_DIR = '.\\output\\'
# LOG_FILE = '.log'
# log_contents = []

# WRITE_LOG = True
PRINT_TO_TERMINAL = False

# def custom_boolean_resolver(self, node):
#     # Return True for any input
#     return True

# # Register the custom resolver
# yaml.resolver.BaseResolver.yaml_implicit_resolvers['tag:yaml.org,2002:bool'] = [custom_boolean_resolver]




def get_components_schemas(spec_data):
    if "components" in spec_data and "schemas" in spec_data["components"]:
        return {'components': {'schemas': spec_data["components"]["schemas"]}}
    else:
        return 0

# Function to determine if $ref is a local reference 
def resolve_ref(spec, ref):
    parts = ref.split('/')
    for part in parts:
        if part == '#':
            # Start from the root
            continue
        spec = spec[part]
    return spec

# Function to recursively resolve local inline schema references 
def resolve_references(spec, root):
    if isinstance(spec, dict):
        if '$ref' in spec:
            ref_value = spec['$ref']
            # Check if the ref is a local reference
            if not ref_value.startswith("#"):
                # Return the spec as is if it's not a local reference
                return spec

            ref_key = ref_value.split('/')[-1]
            refs_encountered.add(ref_key)
            return resolve_references(resolve_ref(root, ref_value), root)
        for key, value in spec.items():
            spec[key] = resolve_references(value, root)
    elif isinstance(spec, list):
        for index, item in enumerate(spec):
            spec[index] = resolve_references(item, root)
    return spec

#  Function to remove referenced schemas from the schemas set
def remove_reference_sources(resolved_data, refs_encountered):
    for ref_key in refs_encountered:
        del resolved_data['components']['schemas'][ref_key]
    return resolved_data

# Extract schema properties (ie. data fields), format, return property and its attributes
def extract_fields_from_schema(schema, components, parent_name=''):
    fields = []
    if PRINT_TO_TERMINAL: print(f'\nschema: {schema}')
    if 'properties' in schema:
        required_properties = schema.get('required', [])
        for property_name, attributes in schema['properties'].items():
            temp_type = attributes.get('type')
            if PRINT_TO_TERMINAL: print(f'Processing attribute: {parent_name}: {property_name}')
            # if no attribute 'type' eg. a $ref, or not an object, or not an array of objects?
            if temp_type is None or \
                temp_type not in ('object') or \
                (temp_type == 'array' and 'properties' not in attributes):     # and array properties not exist?
                # combine various attribute definitions to the format output field
                format_value = attributes.get('format', '')
                format_value = f'format: {format_value}' if format_value else ''
                if 'enum' in attributes:
                    # enum_values = ', '.join(attributes['enum']) # to string for values that may be keywords
                    format_value += (", " if format_value else "") + (f'enum{attributes["enum"]}')
                    if PRINT_TO_TERMINAL: print(format_value)
                if 'minLength' in attributes:
                    min_length_value = str(attributes['minLength'])
                    format_value += (", " if format_value else "") + f'minLength={min_length_value}'
                if 'maxLength' in attributes:
                    max_length_value = str(attributes['maxLength'])
                    format_value += (", " if format_value else "") + f'maxLength={max_length_value}'
                if 'pattern' in attributes:
                    pattern_value = str(attributes['pattern'])
                    format_value += (", " if format_value else "") + f'pattern={pattern_value}'
                if 'nullable' in attributes:
                    nullable_value = str(attributes['nullable'])
                    format_value += (", " if format_value else "") + f'nullable={nullable_value}'

                if '$ref' in attributes:
                    ref_value = attributes['$ref']
                    print(ref_value)
                    # if re.match(r'^https?://', ref_value):  # Check if the $ref is a URL
                    if not ref_value.startswith('#'):  # if $ref is not an inline/local reference, add the ref details
                        fields.append({
                            'Parent': parent_name if parent_name else "N/A",
                            'Field': property_name + ': ' + ref_value,
                            'Description': 'Not a local reference. Add schemas from referenced file to target file definition.',
                            'Type': 'N/A',
                            'Format': 'N/A',
                            'Required': 'N/A',
                            'Default': 'N/A',
                            'Example': 'N/A'
                        })
                        continue
                    else:
                        ref_name = ref_value.split('/')[-1]
                        ref_schema = components['schemas'][ref_name]
                        fields.extend(extract_fields_from_schema(ref_schema, components,
                                                                f"{parent_name}.{property_name}" if parent_name else property_name))
                        continue

                field_data = {
                    'Parent': parent_name if parent_name else "N/A",
                    'Field': property_name,
                    'Description': attributes.get('description', 'N/A'),
                    'Type': attributes.get('type', 'N/A'),
                    'Format': format_value if format_value else 'N/A',
                    'Required': 'Yes' if property_name in required_properties else 'No',
                    'Default': attributes.get('default', 'N/A'),
                    'Example': attributes.get('example', 'N/A')
                }

                fields.append(field_data)

            if attributes.get('type') == 'object':
                fields.extend(extract_fields_from_schema(attributes, components,
                                                         f"{parent_name}.{property_name}" if parent_name else property_name))
            elif attributes.get('type') == 'array' and 'items' in attributes:
                fields.extend(extract_fields_from_schema(attributes['items'], components,
                                                         f"{parent_name}.{property_name}" if parent_name else property_name))

    return fields

# Function to process each schema 
def convert_schema_fields_to_matrix(components):
    schemas = components.get('schemas', {})
    all_fields = []

    for schema_name, schema_details in schemas.items():
        if schema_details.get('type') == 'array' and 'items' in schema_details:
            all_fields.extend(extract_fields_from_schema(schema_details['items'], components, schema_name))
        else:
            all_fields.extend(extract_fields_from_schema(schema_details, components, schema_name))

    return all_fields


#  Function to convert the fields list to CSV rows
def format_as_csv(fields):
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fields[0].keys())
    writer.writeheader()
    for field in fields:
        writer.writerow(field)
    return output.getvalue()

# Function to write the CSV fields rows to file
def write_csv_to_file(fields, csv_output_file):
    csv_output_file = csv_output_file + '.csv'
    try:
        with open(csv_output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields[0].keys())
            writer.writeheader()
            for field in fields:
                writer.writerow(field)
        print(f"Data written to {csv_output_file}")
    except Exception as e:
       print(f"Error writing to file: {e}")


# class to set the alias pointers to not be included in YAML dump
class NoAliasDumper(yaml.Dumper):
    def ignore_aliases(self, data):
        return True


def get_paths(spec_data):
    if "paths" in spec_data:
        return {'paths': spec_data["paths"]}
    else:
        return 0

def get_paths_responses(paths_responses_spec_data):
    if "responses" in paths_responses_spec_data:
        return {'responses': paths_responses_spec_data['responses']}
    else:
        return 0

############################################################################################
############################################################################################


# The OpenApi specification YAML file to extract the properties/fields from.
filename = 'EQL-aws-search-system-1.0.0-swagger - inverters only.yaml'
# filename = 'EQL-portal-services-1.1.0-swagger-pre-resolved - extended defs.yaml'
# test_spec_1.yaml Outage-1.0.0-swagger petstore simple2 EQL-portal-services-1.1.0-swagger

# The folder where the spec file is location relative to the python interpreter


# log_file = f'{filename}-log.txt'
# log_entries = []

print(f'Processing file: {INPUT_DIR}{filename}')
# Load both Swagger specification and data from a single file
with open(INPUT_DIR + filename, 'r') as data_file:
    data = yaml.safe_load(data_file)

# Get the schemas
schema_data = get_components_schemas(data)

# Create a set to track the found inline references
refs_encountered = set()

print(f'Resolving references ...')
# Resolve the references
resolved_data = resolve_references(schema_data, schema_data)

# Remove the sources of references
resolved_data_clean = remove_reference_sources(resolved_data, refs_encountered)

# paths_data = get_paths(data)
# for path in paths_data['paths']:
#     for response_name, response_value in path['responses']['get']:
#         print(response_name)

# # Write the resolved schema components to file as YAML
# with open(OUTPUT_DIR + filename, 'w') as resolved_file:
#     yaml.dump(resolved_data_clean, resolved_file, default_flow_style=False, sort_keys=False, Dumper=NoAliasDumper)

print(f'Extracting and formatting data ...')
# extract the specification data fields and their properties and format as a tabular data specification
fields = convert_schema_fields_to_matrix(resolved_data_clean['components'])


# Create a CSV data filename
csv_data = format_as_csv(fields)

if PRINT_TO_TERMINAL:
    for field in fields:
        print(field)

# convert the schema properties spec to CSV format and save to file
write_csv_to_file(fields, OUTPUT_DIR + filename)

# TODO
# bug with an object in an array - actually not, my bad with formatting excel file. DONE
# logging
# add parent array / repeatable type to indicate more than 1 instance of objects/elements
# omit non data objects and arrays. DONE , not extensively tested.
# tariffs and meters: array of strings , need to fix output. see example below. if items, get item.type, add as 'type: array(string)' or similar
# have made an assumption that a referenced schema is not associated with other operations, this may be incorrect
# handle all data attribute types
# resolve refs in other local files
# write exceptions etc to log file
# dont output non referenced schemas
# add exception handling, yaml parsing, file ops, field formatting, etc.
# handle https, files ?
# handle unreferenced schemas
# parse ref'd files and insert into target
# 
# refs spec - Using $ref (swagger.io)
# data types - Data Types (swagger.io)
# OpenAPI-Specification/versions/3.0.0.md at main · OAI/OpenAPI-Specification · GitHub
# 
# tariffs:
#     type: array
#     items:
#         type: string
#     description: List of current Tariffs for that NMI. For detailed info about Services/Meters/Tariffs/PriceOptions call Get Meter API.
#     example: ['8400', '7200', '9900'] 


# def resolve_references(spec, root):
#     """Recursively resolve references in the spec."""
#     if isinstance(spec, dict):
#         if '$ref' in spec:
#             ref_value = spec['$ref']
#             # Extract the key (e.g., MailingAddress from '#/components/schemas/MailingAddress')
#             ref_key = ref_value.split('/')[-1]
#             refs_encountered.add(ref_key)
#             # Replace the current dict with the resolved ref
#             return resolve_references(resolve_ref(root, ref_value), root)
#         for key, value in spec.items():
#             spec[key] = resolve_references(value, root)
#     elif isinstance(spec, list):
#         for index, item in enumerate(spec):
#             spec[index] = resolve_references(item, root)
#     return spec


# try:
#     with open('example.txt', 'w') as file:
#         file.write("Hello, world!\n")
# except PermissionError:
#     print("You don't have permission to write to the file.")
# except IOError:
#     print("An I/O error occurred while writing to the file.")
# except Exception as e:
#     print(f"An error occurred: {e}")