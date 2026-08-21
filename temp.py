import os
import glob

PARENT_MODELS_DIR = r"E:\Project Jatayu\Parent_Models\temp"
CHILD_MODELS_DIR = r"E:\Project Jatayu\Child_Models_best_pt"

def get_format_sizes(directory_path):
    pt_files = glob.glob(os.path.join(directory_path, "*.pt"))
    int8_onnx_files = glob.glob(os.path.join(directory_path, "*_int8.onnx"))
    
    pt_bytes = sum(os.path.getsize(f) for f in pt_files)
    int8_bytes = sum(os.path.getsize(f) for f in int8_onnx_files)
    
    return len(pt_files), pt_bytes, len(int8_onnx_files), int8_bytes

# Gather metrics
p_pt_count, p_pt_bytes, p_int8_count, p_int8_bytes = get_format_sizes(PARENT_MODELS_DIR)
c_pt_count, c_pt_bytes, c_int8_count, c_int8_bytes = get_format_sizes(CHILD_MODELS_DIR)

# Calculations
total_pt_bytes = p_pt_bytes + c_pt_bytes
total_int8_bytes = p_int8_bytes + c_int8_bytes

total_pt_mb = total_pt_bytes / (1024 * 1024)
total_int8_mb = total_int8_bytes / (1024 * 1024)

# Output Summary Table
print("\n" + "="*60)
print("       QUANTIZED INT8 ONNX vs PYTORCH (.PT) COMPARISON       ")
print("="*60)
print(f"Parent Models (.pt)        [{p_pt_count} files]   : {p_pt_bytes / (1024 * 1024):.2f} MB")
print(f"Parent Models (*_int8.onnx)[{p_int8_count} files]   : {p_int8_bytes / (1024 * 1024):.2f} MB")
print("-" * 60)
print(f"Child Models  (.pt)        [{c_pt_count} files]  : {c_pt_bytes / (1024 * 1024):.2f} MB")
print(f"Child Models  (*_int8.onnx)[{c_int8_count} files]  : {c_int8_bytes / (1024 * 1024):.2f} MB")
print("="*60)
print(f"TOTAL .PT STORAGE         : {total_pt_mb:.2f} MB ({total_pt_bytes / (1024**3):.2f} GB)")
print(f"TOTAL INT8 ONNX STORAGE   : {total_int8_mb:.2f} MB ({total_int8_bytes / (1024**3):.2f} GB)")

if total_pt_bytes > 0:
    diff_mb = total_pt_mb - total_int8_mb
    reduction_pct = (diff_mb / total_pt_mb) * 100
    print(f"SAVINGS VS .PT            : {diff_mb:.2f} MB saved ({reduction_pct:.2f}% reduction)")
print("="*60)