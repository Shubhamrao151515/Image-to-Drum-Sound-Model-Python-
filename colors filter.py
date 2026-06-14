import os
import shutil
import colorsys

# Input folder (0.25 sec wav files)
input_folder = r"D:\project file\New folder (3)\cut_0.25_sec"

# Output folder
output_folder = r"D:\project file\New folder (3)\color_160_samples"
os.makedirs(output_folder, exist_ok=True)

# Get wav files
wav_files = sorted([
    f for f in os.listdir(input_folder)
    if f.lower().endswith(".wav")
])

total_files = len(wav_files)

if total_files != 160:
    print(f"⚠️ Warning: Found {total_files} files, expected 160")

for i, file in enumerate(wav_files):
    # Generate unique color using HSV
    hue = i / total_files          # 0.0 → 1.0
    saturation = 0.9
    value = 0.9

    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)

    # Convert to 0-255 RGB
    r, g, b = int(r*255), int(g*255), int(b*255)

    color_name = f"rgb_{r}_{g}_{b}"

    color_dir = os.path.join(output_folder, color_name)
    os.makedirs(color_dir, exist_ok=True)

    src = os.path.join(input_folder, file)
    dst = os.path.join(color_dir, file)

    shutil.copy(src, dst)

    print(f"{i+1:03d}/160 → {color_name} → {file}")

print("🎨 160 WAV files divided into 160 unique color folders!")
