import os
import librosa
import soundfile as sf

# Folder where WAV files already exist
input_folder = r"D:\project file\New folder (3)\archive (2)"

# Output folder
output_folder = r"D:\project file\New folder (3)\cut_0.25_sec"
os.makedirs(output_folder, exist_ok=True)

CUT_DURATION = 0.25  # seconds

# Walk through all subfolders
for root, dirs, files in os.walk(input_folder):
    for file in files:
        if file.lower().endswith(".wav"):
            input_path = os.path.join(root, file)

            try:
                # Load audio
                audio, sr = librosa.load(input_path, sr=None)

                # Cut first 0.25 sec
                samples = int(sr * CUT_DURATION)
                cut_audio = audio[:samples]

                # Save output
                output_path = os.path.join(output_folder, file)
                sf.write(output_path, cut_audio, sr)

                print(f"Processed: {file}")

            except Exception as e:
                print(f"❌ Error with {file}: {e}")

print("✅ All WAV files cut to 0.25 seconds successfully!")
