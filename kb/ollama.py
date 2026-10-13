"""Start the pinned Ollama on its own port, talk to it over HTTP, and stop it again."""

import json
import os
import socket
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "tools" / "ollama" / "bin" / "ollama"
MODELS = ROOT / "models"


class Client:
    """A connection to one running Ollama server."""

    def __init__(self, base_url: str, context: int) -> None:
        """`context` is the number of tokens the model may read at once."""
        self.base_url = base_url
        self.context = context

    def post(self, path: str, body: dict) -> dict:
        """Send `body` as JSON to an Ollama endpoint and return its JSON reply."""
        request = urllib.request.Request(self.base_url + path, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=3600) as response:
            return json.loads(response.read())

    def chat(self, model: str, prompt: str, schema: dict) -> dict:
        """One reply from the model, forced into the JSON `schema`, parsed. Temperature 0: repeatable."""
        reply = self.post("/api/chat", {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": self.context},
        })
        return json.loads(reply["message"]["content"])

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """One vector per text, asked for in batches of 32."""
        vectors = []
        for start in range(0, len(texts), 32):
            vectors += self.post("/api/embed", {"model": model, "input": texts[start:start + 32]})["embeddings"]
        return vectors

    def pull(self, model: str) -> None:
        """Download a model into models/ when it is not there yet; quick when it is."""
        self.post("/api/pull", {"model": model, "stream": False})


def free_port() -> int:
    """A port nobody on this computer is using, so kb-builder never meets another Ollama."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def running(gpus: str, context: int):
    """The pinned Ollama, started for this run only on the given GPUs, and always stopped afterwards.

    Its output goes to ollama.log in the repository folder.
    """
    if not BINARY.is_file():
        raise FileNotFoundError(f"{BINARY} is missing. Run the start script on this computer first.")
    port = free_port()
    env = dict(os.environ, OLLAMA_HOST=f"127.0.0.1:{port}", OLLAMA_MODELS=str(MODELS),
               CUDA_VISIBLE_DEVICES=gpus, CUDA_DEVICE_ORDER="PCI_BUS_ID")
    with (ROOT / "ollama.log").open("a", encoding="utf-8") as log:
        server = subprocess.Popen([str(BINARY), "serve"], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            client = Client(f"http://127.0.0.1:{port}", context)
            wait_until_up(client, server)
            yield client
        finally:
            server.terminate()
            server.wait(timeout=30)


def wait_until_up(client: Client, server: subprocess.Popen, seconds: int = 60) -> None:
    """Wait until Ollama answers; stop with a clear message when it crashes or takes too long."""
    for _ in range(seconds):
        if server.poll() is not None:
            raise RuntimeError("Ollama stopped while starting. See ollama.log in the repository folder.")
        try:
            urllib.request.urlopen(client.base_url + "/api/version", timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError("Ollama did not start within a minute. See ollama.log in the repository folder.")
