import os
import subprocess
import shutil
import pandas as pd
from PIL import Image, ImageOps
from bs4 import BeautifulSoup

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
    output_files = []
    for file in os.listdir(part_dir):
        if file.endswith(f".{output_format}"):
            file_path = os.path.join(part_dir, file)
            shutil.copy(file_path, output_dir)
            output_files.append(file_path)
    return output_files

def stitch_pngs(png_files, output_path):
    images = [Image.open(png) for png in png_files]
    
    # Calculate max width and total height for the stitched image
    max_width = max(image.width for image in images)
    total_height = sum(image.height for image in images)
    
    # Create a new blank image with the calculated size
    stitched_image = Image.new('RGB', (max_width, total_height), color=(255, 255, 255))
    
    # Paste each image into the stitched image with white padding if necessary
    current_y = 0
    for image in images:
        padded_image = ImageOps.expand(image, (0, 0, max_width - image.width, 0), fill=(255, 255, 255))
        stitched_image.paste(padded_image, (0, current_y))
        current_y += image.height
    
    # Save the stitched image
    stitched_image.save(output_path)

def combine_boms(parts, output_dir, root_dir):
    combined_bom = None

    for part in parts:
        part_bom_path = os.path.join(root_dir, part, f'{part}.bom.tsv')
        if os.path.exists(part_bom_path):
            part_bom = pd.read_csv(part_bom_path, sep='\t')
            if combined_bom is None:
                combined_bom = part_bom
            else:
                combined_bom = pd.concat([combined_bom, part_bom])

    if combined_bom is not None:
        # Group by Description and combine Qty and Designators, removing duplicates
        combined_bom = combined_bom.groupby('Description', as_index=False).agg({
            'Qty': 'sum',
            'Designators': lambda x: ', '.join(sorted(set(', '.join(x).split(', '))))
        })

        combined_bom_path = os.path.join(output_dir, 'combined_bom.tsv')
        combined_bom.to_csv(combined_bom_path, sep='\t', index=False)

    return combined_bom


def combine_htmls(parts, output_dir, root_dir):
    combined_html = None

    for part in parts:
        part_html_path = os.path.join(output_dir, f'{part}.html')
        print(f"Processing {part_html_path}")  # Debug print
        if os.path.exists(part_html_path):
            with open(part_html_path, 'r') as file:
                soup = BeautifulSoup(file, 'html.parser')
                diagram_div = soup.find('div', id='diagram')
                if diagram_div is None:
                    print(f"No diagram found in {part_html_path}")
                    continue
                
                if combined_html is None:
                    combined_html = soup
                    combined_diagram_div = combined_html.find('div', id='diagram')
                    if combined_diagram_div:
                        combined_diagram_div.clear()
                    else:
                        print(f"No combined diagram div found in {part_html_path}")
                        continue
                
                print(f"Appending content from {part_html_path}")  # Debug print
                for content in diagram_div.contents:
                    combined_diagram_div.append(content)

    if combined_html:
        print("HTML combination successful")
    else:
        print("HTML combination failed or no content found")

    return combined_html



def insert_bom_to_html(combined_bom, combined_html):
    bom_div = combined_html.find('div', id='bom')
    bom_table = bom_div.find('table')

    for idx, row in combined_bom.iterrows():
        tr = combined_html.new_tag('tr')
        td_id = combined_html.new_tag('td', attrs={'class': 'bom_col_id'})
        td_description = combined_html.new_tag('td', attrs={'class': 'bom_col_description'})
        td_qty = combined_html.new_tag('td', attrs={'class': 'bom_col_qty'})
        td_unit = combined_html.new_tag('td', attrs={'class': 'bom_col_unit'})
        td_designators = combined_html.new_tag('td', attrs={'class': 'bom_col_designators'})
        
        td_id.string = str(idx + 1)
        td_description.string = row['Description']
        td_qty.string = str(row['Qty'])
        td_unit.string = row.get('Unit', '')
        td_designators.string = row['Designators']

        tr.extend([td_id, td_description, td_qty, td_unit, td_designators])
        bom_table.append(tr)

def main():
    # Load environment file
    env = load_environment_file('harness-output.yml')
    
    # Set root directory
    root_dir = env['PROJECT_NAME']
    
    # Create output directory within the root directory
    output_dir = create_output_dir(root_dir, env['OUTPUT_DIR'])
    
    # List to hold PNG files if output format is png
    png_files = []
    
    # Process each part
    for part in env['PARTS']:
        # Run wireviz command within the root directory
        run_wireviz(part, root_dir)
        
        # Copy the output files to the output directory within the root directory
        files = copy_files_with_extension(part, env['OUTPUT_FORMAT'], output_dir, root_dir)
        
        if env['OUTPUT_FORMAT'] == 'png':
            png_files.extend(files)
    
    # If the output format is PNG, stitch the images together
    if env['OUTPUT_FORMAT'] == 'png' and png_files:
        output_path = os.path.join(root_dir, f"{root_dir}-harness.png")
        stitch_pngs(png_files, output_path)
        
    # Combine BOMs if needed
    combined_bom = None
    if env.get('COMBINE_BOM', 'false').lower() == 'true':
        combined_bom = combine_boms(env['PARTS'], output_dir, root_dir)
    
    # If the output format is HTML, combine HTML and generate BOM
    if env['OUTPUT_FORMAT'] == 'html':
        combined_html = combine_htmls(env['PARTS'], output_dir, root_dir)
        if combined_html:
            insert_bom_to_html(combined_bom, combined_html)
            final_html_path = os.path.join(output_dir, f"{root_dir}-harness.html")
            with open(final_html_path, 'w') as file:
                file.write(str(combined_html))

if __name__ == "__main__":
    main()
