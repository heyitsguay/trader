# trader
A text-based trading game in the terminal, with traders powered by local LLMs!

## Overview

In _trader_, a Player travels between Locations in a World, buying and selling Goods by interacting with Farmers. Start from nothing and earn your fortune through savvy buying and selling. Negotiate with LLM-powered Farmers to persuade, cajole, lie, cheat, and steal your way to riches!

## Setup
### Game setup
Create a virtual environment with Python 3.10+ and install this project's requirements.

From the _trader_ repo root directory:
```
python3 -m venv [desired venv location]/trader
source [desired venv location]/trader/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
```

### LLM server setup

This game's LLM operations use the [Gemma-2-9B-It-SPPO-Iter3](https://huggingface.co/UCLA-AGI/Gemma-2-9B-It-SPPO-Iter3) model, running inference via the [text-generation-webui](https://github.com/oobabooga/text-generation-webui) API server.

Follow the _text-generation-webui_ setup instructions on a computer or cloud instance of your choice with an NVIDIA GPU with 24GB VRAM. _trader_ has been tested on a 3090Ti. Once _text-generation-webui_ is set up, start the server by activating the conda env you create during setup, `cd`ing to the _text-generation-webui_ root directory, and running
```
python server.py --api --listen
```
It is recommended to do this in a terminal you can detach from without ending the process, e.g. using `tmux` or `screen`.

Once running, open the server's local URL in your browser (by default, `http://0.0.0.0:7860`) and switch to the **Model** tab at the top of the page. Download the inference LLM by entering `UCLA-AGI/Gemma-2-9B-It-SPPO-Iter3` into the **Download model or LoRA** text box and click **Download**. When the download completes, load the model from the **Model** dropdown on the left (you may need to refresh the list). If the model loads successfully, you will see
```
Successfully loaded UCLA-AGI_Gemma-2-9B-It-SPPO-Iter3.
```
At this point, note the API URL (by default, `http://0.0.0.0:5000`). _trader_ requests will route to `${API_URL}/v1/chat/completions`. This URL will only work if you are playing _trader_ on the same machine where you are running _text-generation-webui_. Using port forwarding, a mesh VPN like Tailscale, or a cloud server, you can connect a remote server running _text-generation-webui_ to your local machine running _trader_, in which case the API URL may not be on _localhost_ (0.0.0.0).

## Play

Once your _trader_ venv is set up, and you have a server running _text-generation-webui_, you can play! Make sure the _trader_ venv is active, navigate to the _trader_ project root, and run
```
python start.py [SEED] [REQUEST URL]
```
Where `[SEED]` is a positive integer, and `[REQUEST URL]` is the URL to send requests to the _text-generation-webui_ server API, e.g. `http://0.0.0.0:5000/v1/chat/completions` if running the server and _trader_ on the same machine.

Move around or Trade with the locals, but beware -- each Move costs money! Also there's not really a failure condition right now. If you run out of sufficient money to do anything you're just stuck and you have to restart.

**This is alpha software**, with no serious intention of ever having a full gameplay experience with no rough edges. Feel free to file issues, I may or may not address them.

