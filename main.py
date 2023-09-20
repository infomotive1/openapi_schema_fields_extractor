import yaml
import csv
from io import StringIO
# import re


def get_components_schemas(spec_data):
    if "components" in spec_data and "schemas" in spec_data["components"]:
        return {'components': {'schemas': spec_data["components"]["schemas"]}}
    else:
        return 0


def resolve_ref(spec, ref):
    parts = ref.split('/')
    for part in parts:
        if part == '#':
            # Start from the root
            continue
        spec = spec[part]
    return spec


class NoAliasDumper(yaml.Dumper):
    def ignore_aliases(self, data):
        return True


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



def remove_reference_sources(resolved_data, refs_encountered):
    for ref_key in refs_encountered:
        del resolved_data['components']['schemas'][ref_key]
    return resolved_data

# Extract schema properties (ie. data fields), format, return property and its attributes
def extract_fields_from_schema(schema, components, parent_name=''):
    fields = []

    if 'properties' in schema:
        required_properties = schema.get('required', [])
        for property_name, attributes in schema['properties'].items():
            # combine various attribute definitions to the format output field
            format_value = attributes.get('format', '')
            format_value = f'format: {format_value}' if format_value else ''
            if 'enum' in attributes:
                enum_values = ', '.join(attributes['enum'])
                format_value += (", " if format_value else "") + f'enum[{enum_values}]'
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
                        'Description': 'URL reference. Add schemas from referenced file to target file definition.',
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


def convert_schema_fields_to_matrix(components):
    schemas = components.get('schemas', {})
    all_fields = []

    for schema_name, schema_details in schemas.items():
        if schema_details.get('type') == 'array' and 'items' in schema_details:
            all_fields.extend(extract_fields_from_schema(schema_details['items'], components, schema_name))
        else:
            all_fields.extend(extract_fields_from_schema(schema_details, components, schema_name))

    return all_fields


def format_as_csv(fields):
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fields[0].keys())
    writer.writeheader()
    for field in fields:
        writer.writerow(field)
    return output.getvalue()


def write_csv_to_file(fields, csv_output_file):
    csv_output_file = csv_output_file + '.csv'
    with open(csv_output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields[0].keys())
        writer.writeheader()
        for field in fields:
            writer.writerow(field)
    print(f"Data written to {csv_output_file}")


############################################################################################
############################################################################################

# The OpenApi specification YAML file to extract the properties/fields from.
filename = 'EQL-portal-services-1.1.0-swagger-pre-resolved - extended defs.yaml'
# test_spec_1.yaml Outage-1.0.0-swagger petstore simple2 EQL-portal-services-1.1.0-swagger

# The folder where the spec file is location relative to the python interpreter
spec_dir = '.\\specs\\'

# Load both Swagger specification and data from a single file
with open(spec_dir + filename, 'r') as data_file:
    data = yaml.safe_load(data_file)

# Get the schemas
data = get_components_schemas(data)

# Create a set to track the found inline references
refs_encountered = set()

# Resolve the references
resolved_data = resolve_references(data, data)

# Remove the sources of references
resolved_data_clean = remove_reference_sources(resolved_data, refs_encountered)

# Write the resolved schema components to file as YAML
with open('resolved_swagger.yaml', 'w') as resolved_file:
    yaml.dump(resolved_data_clean, resolved_file, default_flow_style=False, sort_keys=False, Dumper=NoAliasDumper)

# extract the specification data fields and their properties and format as a tabular data specification
fields = convert_schema_fields_to_matrix(resolved_data_clean['components'])

# Create a CSV data filename
csv_data = format_as_csv(fields)

for field in fields:
    print(field)

# convert the schema properties spec to CSV format and save to file
write_csv_to_file(fields, filename)