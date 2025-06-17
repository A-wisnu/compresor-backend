from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import zipfile
import io
import os
from PIL import Image
import json
import pikepdf

app = Flask(__name__)
CORS(app, expose_headers=['compression-results'])

def get_file_size(file_storage):
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    return size

@app.route('/compress', methods=['POST'])
def compress_files():
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400

    zip_buffer = io.BytesIO()
    compression_results = []

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files:
            original_filename = file.filename
            original_size = get_file_size(file)
            file.seek(0)
            
            base_filename, file_ext = os.path.splitext(original_filename)
            file_ext = file_ext.lower()
            
            # 1. PDF Compression
            if file_ext == '.pdf':
                try:
                    pdf = pikepdf.open(file)
                    compressed_buffer = io.BytesIO()
                    pdf.save(compressed_buffer, 
                             object_stream_mode=pikepdf.ObjectStreamMode.generate, 
                             compress_streams=True,
                             linearize=True)  # Optimize for web viewing
                    
                    compressed_size = compressed_buffer.tell()
                    compressed_buffer.seek(0)
                    
                    zipf.writestr(original_filename, compressed_buffer.read())
                    compression_results.append({
                        'filename': original_filename, 
                        'original_size': original_size, 
                        'compressed_size': compressed_size
                    })
                    continue
                except Exception as e:
                    print(f"Error compressing PDF: {str(e)}")
                    file.seek(0)  # Reset pointer if failed

            # 2. Image Compression
            if file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']:
                try:
                    img = Image.open(file)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')

                    compressed_buffer = io.BytesIO()
                    
                    # Use different compression settings based on image type
                    if file_ext in ['.png', '.gif']:
                        quality = 85  # Higher quality for PNG and GIF
                        format_to_save = 'PNG' if file_ext == '.png' else 'JPEG'
                        new_filename = f"{base_filename}.png" if file_ext == '.png' else f"{base_filename}.jpg"
                    else:
                        quality = 80  # Standard quality for JPEG and others
                        format_to_save = 'JPEG'
                        new_filename = f"{base_filename}.jpg"
                    
                    # Resize large images to reduce size further
                    max_dimension = 2000  # Maximum dimension in pixels
                    if max(img.size) > max_dimension:
                        ratio = max_dimension / max(img.size)
                        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                        img = img.resize(new_size, Image.LANCZOS)
                    
                    img.save(compressed_buffer, 
                             format=format_to_save, 
                             quality=quality, 
                             optimize=True)
                    
                    compressed_size = compressed_buffer.tell()
                    compressed_buffer.seek(0)
                    
                    # Only use the compressed version if it's actually smaller
                    if compressed_size < original_size:
                        zipf.writestr(new_filename, compressed_buffer.read())
                        compression_results.append({
                            'filename': original_filename, 
                            'original_size': original_size, 
                            'compressed_size': compressed_size
                        })
                    else:
                        # If compression didn't reduce size, use original
                        file.seek(0)
                        zipf.writestr(original_filename, file.read())
                        compression_results.append({
                            'filename': original_filename, 
                            'original_size': original_size, 
                            'compressed_size': original_size
                        })
                    continue
                except Exception as e:
                    print(f"Error compressing image: {str(e)}")
                    file.seek(0)  # Reset pointer if failed

            # 3. Default compression for other file types
            try:
                file.seek(0)
                zipf.writestr(original_filename, file.read())
                compression_results.append({
                    'filename': original_filename, 
                    'original_size': original_size, 
                    'compressed_size': original_size
                })
            except Exception as e:
                print(f"Error adding file to ZIP: {str(e)}")

    zip_buffer.seek(0)
    
    response = send_file(
        zip_buffer,
        as_attachment=True,
        download_name='compressed_files.zip',
        mimetype='application/zip'
    )

    # Use URL encoding to ensure proper JSON transmission in headers
    response.headers['compression-results'] = json.dumps(compression_results)
    
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5001) 