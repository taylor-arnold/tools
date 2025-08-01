import parselmouth
import numpy as np
import json

import parselmouth
import matplotlib.pyplot as plt
import numpy as np
from typing import Tuple, List, Optional


def extract_f1_f2_confident(wave_file_path: str, 
                           time_step: Optional[float] = None,
                           max_formant: float = 5500.0,
                           num_formants: int = 5,
                           window_length: float = 0.025,
                           pre_emphasis: float = 50.0,
                           intensity_threshold: float = 50.0,
                           voicing_threshold: float = 0.5) -> Tuple[List[float], List[float], List[float]]:
    """
    Extract F1 and F2 formants from a wave file using parselmouth, 
    returning only confident measurements (where Praat would plot formants).
    
    Parameters:
    -----------
    wave_file_path : str
        Path to the wave file
    time_step : Optional[float], default=None
        Time step for analysis (None = auto)
    max_formant : float, default=5500.0
        Maximum formant frequency to search for (Hz)
    num_formants : int, default=5
        Number of formants to extract
    window_length : float, default=0.025
        Window length for formant analysis (seconds)
    pre_emphasis : float, default=50.0
        Pre-emphasis frequency (Hz)
    intensity_threshold : float, default=50.0
        Minimum intensity threshold (dB) for confident measurements
    voicing_threshold : float, default=0.5
        Minimum voicing strength (0-1) for confident measurements
    
    Returns:
    --------
    Tuple[List[float], List[float], List[float]]
        (times, f1_values, f2_values) - all filtered for confident measurements
    """
    
    # Load the sound file
    try:
        sound = parselmouth.Sound(wave_file_path)
    except Exception as e:
        raise ValueError(f"Could not load audio file: {e}")
    
    # Extract formants
    formant_kwargs = {
        'max_number_of_formants': num_formants,
        'maximum_formant': max_formant,
        'window_length': window_length,
        'pre_emphasis_from': pre_emphasis
    }
    
    # Only add time_step if it's not None
    if time_step is not None:
        formant_kwargs['time_step'] = time_step
        
    formants = sound.to_formant_burg(**formant_kwargs)
    
    # Extract pitch for voicing information
    pitch = sound.to_pitch()
    
    # Extract intensity
    intensity = sound.to_intensity()
    
    # Get time points from formant object
    times = formants.xs()
    
    confident_times = []
    confident_f1 = []
    confident_f2 = []
    
    for i, time in enumerate(times):
        try:
            # Get formant values at this time point
            f1 = formants.get_value_at_time(formant_number=1, time=time)
            f2 = formants.get_value_at_time(formant_number=2, time=time)

            # Get pitch (fundamental frequency) at this time
            f0 = pitch.get_value_at_time(time)

            # Get intensity at this time
            intensity_db = intensity.get_value(time)

            # Check if this point should be considered "confident"
            # Similar to Praat's criteria for plotting formants
            
            # 1. Must have valid formant values (not NaN or undefined)
            if np.isnan(f1) or np.isnan(f2) or f1 <= 0 or f2 <= 0:
                continue
                
            # 2. Must have sufficient intensity
            if np.isnan(intensity_db) or intensity_db < intensity_threshold:
                continue
                
            # 3. Must have voicing (valid F0)
            if np.isnan(f0) or f0 <= 0:
                continue
                
            # 4. Formants should be in reasonable ranges and order
            if f1 >= f2 or f1 < 200 or f2 < 500:
                continue
                
            # 5. Additional voicing strength check using pitch strength
            pitch_strength = pitch.get_value_at_time(time)
            if np.isnan(pitch_strength) or pitch_strength < voicing_threshold:
                continue
            
            # If all checks pass, this is a confident measurement
            confident_times.append(time)
            confident_f1.append(f1)
            confident_f2.append(f2)
            
        except Exception as e:
            continue
    
    return confident_times, confident_f1, confident_f2


def extract_f1_f2_confident_with_details(wave_file_path: str, **kwargs) -> dict:
    """
    Extended version that returns additional information for analysis.
    
    Returns:
    --------
    dict
        Dictionary containing times, f1, f2, and additional analysis details
    """
    
    times, f1, f2 = extract_f1_f2_confident(wave_file_path, **kwargs)
    
    return {
        'times': times,
        'f1': f1,
        'f2': f2,
        'num_points': len(times),
        'duration': max(times) - min(times) if times else 0,
        'mean_f1': np.mean(f1) if f1 else np.nan,
        'mean_f2': np.mean(f2) if f2 else np.nan,
        'std_f1': np.std(f1) if f1 else np.nan,
        'std_f2': np.std(f2) if f2 else np.nan
    }


def plot_formants_with_words(times, f1_values, f2_values,
                             word_starts, word_ends, words,
                             output_pdf="formants_with_words.pdf"):
    """
    Plot F1 and F2 formants with annotated spoken words.

    Parameters:
    - times, f1_values, f2_values: Formant data (filtered).
    - word_starts, word_ends (list of float): Start and end times for each word.
    - words (list of str): Spoken word strings.
    - output_pdf (str): Output PDF filename.
    """
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 6))

    # Plot F1 and F2
    plt.plot(times, f1_values, label="F1", marker='o', linestyle='')
    plt.plot(times, f2_values, label="F2", marker='x', linestyle='')

    # Annotate words
    ymin, ymax = plt.ylim()
    y_text = ymax + (ymax - ymin) * 0.05  # position for text slightly above the plot

    for start, end, word in zip(word_starts, word_ends, words):
        plt.hlines(
            y=y_text, xmin=start, xmax=end, color="gray", linestyles="dotted"
        )
        plt.plot(start, y_text, 'o', color='gray')
        plt.plot(end, y_text, 'o', color='gray')

        plt.text((start + end) / 2, y_text + (ymax - ymin) * 0.02, word,
                 ha='center', va='bottom', fontsize=10)

    # Final formatting
    plt.xlabel("Time (s)")
    plt.ylabel("Frequency (Hz)")
    plt.title("Formant Frequencies with Word Annotations")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_pdf)
    plt.close()


def plot_formats(json_file="output.json", wav_file="output.wav", output_pdf="output.pdf"):

    with open(json_file, 'r') as file:
        data = json.load(file)

    startTime = [x['startTime'] for x in data['segments']]
    endTime = [x['endTime'] for x in data['segments']]
    wordVal = [x['text'] for x in data['segments']]

    times, f1, f2 = extract_f1_f2_confident(wav_file)
    plot_formants_with_words(
        times, f1, f2, startTime, endTime, wordVal, output_pdf=output_pdf
    )


