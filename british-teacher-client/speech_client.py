import os
import uuid
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

OUTPUT_DIR = Path(__file__).parent / "static" / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def synthesize_text_to_wav(text: str) -> str:
    """Synthesize `text` to a wav file and return the relative URL path.

    Requires `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` in environment.
    """
    if not SPEECH_KEY or not SPEECH_REGION:
        raise RuntimeError("Azure Speech credentials not configured (AZURE_SPEECH_KEY/AZURE_SPEECH_REGION)")

    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    # Use a neutral British voice by default
    speech_config.speech_synthesis_voice_name = "en-GB-LibbyNeural"

    filename = f"tts_{uuid.uuid4().hex}.wav"
    out_path = OUTPUT_DIR / filename

    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(out_path))
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    result = synthesizer.speak_text_async(text).get()
    if hasattr(synthesizer, 'close'):
        synthesizer.close()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        # Return URL path relative to static folder
        return f"/static/audio/{filename}"

    if result.reason == speechsdk.ResultReason.Canceled:
        cancellation = speechsdk.CancellationDetails.from_result(result)
        raise RuntimeError(
            f"Speech synthesis failed: {result.reason}. "
            f"CancellationReason={cancellation.reason}. "
            f"ErrorDetails={cancellation.error_details}"
        )

    raise RuntimeError(f"Speech synthesis failed: {result.reason}")
