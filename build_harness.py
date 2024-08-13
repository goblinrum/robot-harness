import os
import subprocess
import shutil
import pandas as pd

def load_environment_file(file_path):
    import yaml
    with open(file_path, 'r') as file:
        env = yaml.safe_load(file)
    return env

def create_output_dir(root_dir, output_dir):
    output_path = os.path.join(root_dir, output_dir)
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    return output_path

def run_wireviz(part_name, root_dir):
    subprocess.run(["wireviz", os.path.join(root_dir, part_name, f"{part_name}.yml")], check=True)

def copy_files_with_extension(part_name, output_format, output_dir, root_dir):
    part_dir = os.path.join(root_dir, part_name)
    for file in os.listdir(part_dir):
        if file.endswith(f".{output_format}"):
            shutil.copy(os.path.join(part_dir, file), output_dir)

def combine_boms(parts, output_dir, root_dir):
    combined_bom = None

    for part in parts:
        part_bom_path = os.path.join(root_dir, part, 'bom.tsv')
        if os.path.exists(part_bom_path):
            part_bom = pd.read_csv(part_bom_path, sep='\t')
            if combined_bom is None:
                combined_bom = part_bom
            else:
                combined_bom = pd.concat([combined_bom, part_bom])

    if combined_bom is not None:
        # Group by Description and combine Qty and Designators
        combined_bom = combined_bom.groupby('Description', as_index=False).agg({
            'Qty': 'sum',
            'Designators': lambda x: ', '.join(x)
        })

        combined_bom_path = os.path.join(output_dir, 'combined_bom.tsv')
        combined_bom.to_csv(combined_bom_path, sep='\t', index=False)

def main():
    # Load environment file
    env = load_environment_file('harness-output.yml')
    
    # Set root directory
    root_dir = env['PROJECT_NAME']
    
    # Create output directory within the root directory
    output_dir = create_output_dir(root_dir, env['OUTPUT_DIR'])
    
    # Process each part
    for part in env['PARTS']:
        # Run wireviz command within the root directory
        run_wireviz(part, root_dir)
        
        # Copy the output files to the output directory within the root directory
        copy_files_with_extension(part, env['OUTPUT_FORMAT'], output_dir, root_dir)
    
    # Combine BOMs if needed
    if env.get('COMBINE_BOM', 'false').lower() == 'true':
        combine_boms(env['PARTS'], output_dir, root_dir)

if __name__ == "__main__":
    main()
