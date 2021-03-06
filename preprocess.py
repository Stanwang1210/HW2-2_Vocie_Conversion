import argparse
import glob
import os
from datetime import datetime

import librosa
import numpy as np
import pyworld

from utility import *

FEATURE_DIM = 36
SAMPLE_RATE = 16000
FRAMES = 512
FFTSIZE = 1024
SPEAKERS_NUM = len(speakers)
CHUNK_SIZE = 1 # concate CHUNK_SIZE audio clips together
EPSILON = 1e-10
MODEL_NAME = 'starganvc_model'
def load_wavs(dataset: str, sr):
    '''
    data dict contains all audios file path &
    resdict contains all wav files
    '''
    data = {}
    files = [f for f in glob.glob(os.path.join(dataset, "**/*.wav"), recursive = True)]
    # print(files)
    # print('hello')
    # raise InterruptedError
    resdict = {}
    for f in files:
        person = f.split('/')[-1].split('_')[0]
        print(f)
        filename = f.split('/')[-1].split('_')[1].split('.')[0]
        if person not in resdict:
            resdict[person] = {}
        wav, sr = librosa.load(f, sr, mono=True, dtype=np.float64) # turn the audio to mono (1 channel)
        y,_ = librosa.effects.trim(wav, top_db=15)
        
        wav = np.append(y[0], y[1:] - 0.97 * y[:-1]) # # Preemphasis
         # Pre-emphasis is a way to boost only the signal's high-frequency components, 
         # while leaving the low-frequency components in their original state. 
         # Pre-emphasis operates by boosting the high-frequency energy every time a transition in the data occurs. 
         # The data edges contain the signal's high-frequency content. 
         # The signal edges deteriorate with the loss of the high-frequency signal components.
         # By https://www.ieee802.org/3/ak/public/dec02/MysticomCX4_Dec0602;6_taich.pdf
         # Y[n] = (1-Preemphasis) * X[n] - Preemphasis * X[n-1] 
        resdict[person][f'{filename}'] = wav
    return resdict

'''
def load_wavs(dataset: str, sr): # sr is Sampleing Rate
    
    #data dict contains all audios file path &
    #resdict contains all wav files   
    
    data = {}
    with os.scandir(dataset) as it: # List all files and diretories in the specified path   
        for entry in it:
            if entry.is_dir(): # the entry is a directory 
                data[entry.name] = [] # the content entr.name is a null list
                # print(entry.name, entry.path)
                with os.scandir(entry.path) as it_f:
                    for onefile in it_f:
                        if onefile.is_file(): # the entry is a audio file
                            # print(onefile.path)
                            data[entry.name].append(onefile.path)
    print(f'loaded keys: {data.keys()}')
    #data like {TM1:[xx,xx,xxx,xxx]}
    resdict = {}

    cnt = 0
    for key, value in data.items():
        resdict[key] = {}

        for one_file in value:
            
            filename = one_file.split('/')[-1].split('.')[0] #like 100061
            newkey = f'{filename}'
            wav, _ = librosa.load(one_file, sr=sr, mono=True, dtype=np.float64) # wave, sr
            y,_ = librosa.effects.trim(wav, top_db=15)
            # librosa.effects.trim(myrecording[fs:], top_db=50, frame_length=256, hop_length=64)
            # Decreasing hop_length effectively increases the resolution for trimming. Decreasing top_db makes the function less sensitive, i.e., low level noise is also regarded as silence. Using a computer microphone, you do probably have quite a bit of low level background noise.
            # If this all does not help, you might want to consider using SOX, or its Python wrapper pysox. It also has a trim function.
            # Update Look at the waveform of your audio. Does it have a spike somewhere at the beginning? Some crack sound perhaps. That will keep librosa from trimming correctly. Perhaps manually throwing away the first second (=fs samples) and then trimming solves the issue:
            wav = np.append(y[0], y[1:] - 0.97 * y[:-1])

            resdict[key][newkey] = wav
            # resdict[key].append(temp_dict) #like TM1:{100062:[xxxxx], .... }
            print('.', end='')
            cnt += 1

    print(f'\nTotal {cnt} aduio files!')
    return resdict
'''
def chunks(iterable, size):
    """Yield successive n-sized chunks from iterable."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]
        # https://www.geeksforgeeks.org/use-yield-keyword-instead-return-keyword-python/

def wav_to_mcep_file(dataset: str, sr=SAMPLE_RATE, processed_filepath: str = './data/processed'):
    '''convert wavs to mcep feature using image repr'''
    shutil.rmtree(processed_filepath)
    os.makedirs(processed_filepath, exist_ok=True)

    allwavs_cnt = len(glob.glob(f'{dataset}/*/*.wav'))
    print(f'Total {allwavs_cnt} audio files!')

    d = load_wavs(dataset, sr)
    # print(f"Dictionary looks like {d.keys()}")
    # stop
    for one_speaker in d.keys():
        values_of_one_speaker = list(d[one_speaker].values())
       
        for index, one_chunk in enumerate (chunks(values_of_one_speaker, CHUNK_SIZE)):
            wav_concated = [] #preserve one batch of wavs
            temp = one_chunk.copy() #return a new copy of chunk
            #print(f'temp looks like {temp}')
            #concate wavs (mainly to unsqueeze the temp)
            for one in temp:
                wav_concated.extend(one) # concat the content of one into wav_concated
            #print(f'wav_concated looks like {wav_concated}')
            wav_concated = np.array(wav_concated)
            # print(temp == wav_concated)
            #process one batch of1 wavs 
            f0, ap, sp, coded_sp = cal_mcep(wav_concated, sr=sr, dim=FEATURE_DIM)
            newname = f'{one_speaker}_{index}'
            file_path_z = os.path.join(processed_filepath, newname)
            np.savez(file_path_z, f0=f0, coded_sp=coded_sp)
            print(f'[save]: {file_path_z}')

            #split mcep t0 muliti files  
            for start_idx in range(0, coded_sp.shape[1] - FRAMES + 1, FRAMES):
                one_audio_seg = coded_sp[:, start_idx : start_idx+FRAMES]

                if one_audio_seg.shape[1] == FRAMES:
                    temp_name = f'{newname}_{start_idx}'
                    filePath = os.path.join(processed_filepath, temp_name)

                    np.save(filePath, one_audio_seg)
                    print(f'[save]: {filePath}.npy')
            
        

def world_features(wav, sr, fft_size, dim):
    f0, timeaxis = pyworld.harvest(wav, sr) # The fundamental period T0 of a voiced speech signal can be
                                            # defined as the elapsed time between two successive laryngeal pulses and the fundamental frequency is F0 = 1/T0 [1].

    sp = pyworld.cheaptrick(wav, f0, timeaxis, sr,fft_size=fft_size) # extract smoothed spectrogram
    ap = pyworld.d4c(wav, f0, timeaxis, sr, fft_size=fft_size) # extract aperiodicity
    # “aperiodicity” is defined as the power ratio between the speech signal and the aperiodic component of the signal.
    coded_sp = pyworld.code_spectral_envelope(sp, sr, dim)

    return f0, timeaxis, sp, ap, coded_sp

def cal_mcep(wav, sr=SAMPLE_RATE, dim=FEATURE_DIM, fft_size=FFTSIZE):
    '''cal mcep given wav singnal
        the frame_period used only for pad_wav_to_get_fixed_frames
    '''
    f0, timeaxis, sp, ap, coded_sp = world_features(wav, sr, fft_size, dim)
    coded_sp = coded_sp.T # dim x n

    return f0, ap, sp, coded_sp


if __name__ == "__main__":
    start = datetime.now()
    parser = argparse.ArgumentParser(description = 'Convert the wav waveform to mel-cepstral coefficients(MCCs)\
    and calculate the speech statistical characteristics')
    
    input_dir = './modified_data/data/speakers'
    output_dir = './modified_data/data/processed'
   
    parser.add_argument('--input_dir', type = str, help = 'the direcotry contains data need to be processed', default = input_dir)
    parser.add_argument('--output_dir', type = str, help = 'the directory stores the processed data', default = output_dir)
    
    argv = parser.parse_args()
    input_dir = argv.input_dir
    output_dir = argv.output_dir

    os.makedirs(output_dir, exist_ok=True)
    
    wav_to_mcep_file(input_dir, SAMPLE_RATE,  processed_filepath=output_dir)

    #input_dir is train dataset. we need to calculate and save the speech\
    # statistical characteristics for each speaker.
    generator = GenerateStatistics(output_dir)
    generator.generate_stats()
    generator.normalize_dataset()
    end = datetime.now()
    print(f"[Runing Time]: {end-start}")
