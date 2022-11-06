import gc
import os
import torch
import whisper
from whisper.tokenizer import LANGUAGES, TO_LANGUAGE_CODE
import tempfile
from utils import slugify, str2bool, write_srt, write_vtt
import yt_dlp
import warnings
import json
import argparse
from tqdm import tqdm

# se tiver que matar coisas que usam vRAM pra rodar o script, tente descomentar isso:
# torch.cuda.empty_cache()
# gc.collect()

# x planejar estruturas de dados
# x pegar lista de videos do youtube
# x gerar lista do que falta transcrever
# x criar status entre-rodadas do programa salvando em arquivo o que foi transcrito
# x brrrr

# tiny 	    39 M
# base 	    74 M
# small 	244 M
# medium 	769 M
# large 	1550 M 
MODEL_SIZE = "medium" 
SUBTITLES_FORMAT = "srt"
# DEVICE = "gpu" # todo: implementar isso

def make_subtitles(videos, model_name="small", output_dir=".", overwriteTitle=None, subtitles_format=SUBTITLES_FORMAT, verbose=False, task="transcribe", language=None, break_lines=0, args={
    "model": MODEL_SIZE,
    "format": SUBTITLES_FORMAT,
    "output_dir": ".",
    "verbose": False,
    "task": "transcribe",
    "language": None,
    "break_lines": 0,
}):
    os.makedirs(output_dir, exist_ok=True)
    if model_name.endswith(".en"):
        warnings.warn(
            f"{model_name} is an English-only model, forcing English detection.")
        language = "en"

    model = whisper.load_model(model_name) #device=DEVICE
    audios = get_audio(videos)

    for title, audio_path in audios.items():
        warnings.filterwarnings("ignore")
        result = model.transcribe(audio_path, verbose=None)
        warnings.filterwarnings("default")
        if overwriteTitle is None:
            overwriteTitle = title
        if (subtitles_format == 'vtt'):
            vtt_path = os.path.join(
                output_dir, f"{slugify(overwriteTitle)}.vtt")
            with open(vtt_path, 'w', encoding="utf-8") as vtt:
                write_vtt(result["segments"], file=vtt,
                          line_length=break_lines)
            return os.path.relpath(vtt_path, os.path.curdir)
        else:
            srt_path = os.path.join(
                output_dir, f"{slugify(overwriteTitle)}.srt")
            with open(srt_path, 'w', encoding="utf-8") as srt:
                write_srt(result["segments"], file=srt,
                          line_length=break_lines)
            return os.path.abspath(srt_path, os.path.curdir)


def get_audio(urls):
    temp_dir = tempfile.gettempdir()
    ydl = yt_dlp.YoutubeDL({
        'quiet': True,
        'verbose': False,
        'format': 'bestaudio',
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        'postprocessors': [{'preferredcodec': 'mp3', 'preferredquality': '192', 'key': 'FFmpegExtractAudio', }],
    })
    paths = {}

    for url in urls:
        result = ydl.extract_info(url, download=True)
        paths[result["title"]] = os.path.join(temp_dir, f"{result['id']}.mp3")
    return paths


def get_state():
    try:
        with open("estado_.json", "r") as sf:
            state = json.load(sf)
    except:
        state = {
            "canais": [
                {
                    "name": "Nome do canal",
                    "url": "https://www.youtube.com/channel/___mude_aqui___"
                }
            ],
            "processados": [

            ]
        }
    return state


def save_state(state):
    with open("estado.json", "w") as sf:
        json.dump(state, sf, indent=4)


def get_channel_updates(channel):
    scraped = []
    resp = ydl.extract_info(channel["url"], download=False)
    for j in resp["entries"]:
        scraped.append({
            "id": j["id"],
            "title": j["title"],
            "duration": j["duration"],
            "duration_string": j["duration_string"],
            "upload_date": j["upload_date"],
        })
    return scraped


def add_to_state(channel: dict, scraped: list):
    ch_proc = None
    for i in range(len(state["processados"])):
        if state["processados"][i]["channel"] == channel["name"]:
            ch_proc = i
            break
    if ch_proc is None:
        state["processados"].append({
            "channel": channel["name"],
            "brrr": [],
            "feito": []
        })
        ch_proc = len(state["processados"])-1

    everyID = [i["id"] for i in [*state["processados"][ch_proc]
                                 ["brrr"], *state["processados"][ch_proc]["feito"]]]
    newStuff = list(filter(lambda x: x["id"] not in everyID, scraped))
    if len(newStuff) == 0:
        print("Nada novo no ", channel["name"])
        return
    for i in newStuff:
        state["processados"][ch_proc]["brrr"].append(i)
    save_state(state)


def update_channel(ch):
    updates = get_channel_updates(ch)
    #updates = [{
    #     "id": "123",
    #     "title": "teste",
    #     "duration": 123,
    #     "duration_string": "123",
    #     "upload_date": "123",
    # }])
    add_to_state(ch, updates)


def transcribe(workspaceIdx):
    vidIdx = 0
    ch_name = state["processados"][workspaceIdx]["channel"]
    vid = state["processados"][workspaceIdx]["brrr"].pop(vidIdx)
    vid["model"] = MODEL_SIZE
    vid["path"] = make_subtitles(
        videos=["https://www.youtube.com/watch?v="+vid["id"]],
        model_name=MODEL_SIZE,
        output_dir=ch_name,
        overwriteTitle="_".join([
            ch_name,
            vid["upload_date"],
            vid["id"],
            str(vid["duration"]),
            vid["title"]
        ]),
        subtitles_format=SUBTITLES_FORMAT,
        verbose=False,
        task="transcribe",
        language="pt",
        break_lines=0)
    state["processados"][workspaceIdx]["feito"].append(vid)
    save_state(state)

state = get_state()
temp_dir = tempfile.gettempdir()
ydl = yt_dlp.YoutubeDL({
    'quiet': True,
    'verbose': False,
    'format': 'bestaudio',
    "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
    'postprocessors': [{'preferredcodec': 'mp3', 'preferredquality': '192', 'key': 'FFmpegExtractAudio', }],
})
if __name__ == '__main__':
    if len(state["canais"]) == 0:
        print("Nenhum canal adicionado, abra o .json e adicione um")
        save_state(state)
        exit()
    # paralelizar, lento demais isso aqui
    for i in state["canais"]:
        update_channel(i)
    # state = get_state()
    # não da pra paralelizar
    for i in range(len(state["processados"])):
        for vid in tqdm(range(len(state["processados"][i]["brrr"]))):
            transcribe(i)
            state = get_state()
