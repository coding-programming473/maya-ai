import array
import asyncio
import os
import signal
import sys
import time

# Windows console cp1252 emoji/fancy characters nahi padh pata - UTF-8 force karein
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Input mode: default MICROPHONE. Ctrl+C = text mode (mic band), wapas Ctrl+C = mic.
# NOTE: heavy imports (pyaudio/genai) se PEHLE install - startup me Ctrl+C dabane par
# default KeyboardInterrupt se app na mare
MODE = "mic"
_last_toggle = 0.0

def _on_sigint(signum, frame):
    global MODE, _last_toggle
    now = time.monotonic()
    # Ek Ctrl+C press kabhi kabhi 2 jagah fire hota hai (handler + input read abort) - debounce
    if now - _last_toggle < 0.6:
        return
    _last_toggle = now
    if MODE == "mic":
        MODE = "text"
        print("\n[TEXT MODE] Mic band - ab type karke message bhej dein.")
        print("            Wapas mic: Ctrl+C | Band: 'exit' likhein\n")
    else:
        MODE = "mic"
        print("\n[MIC MODE] Mic chalu - ab boliye.")
        print("           Text mode: Ctrl+C | Band: 'exit' likhein\n")

signal.signal(signal.SIGINT, _on_sigint)

import pyaudio
import audioop  # stdlib - 48k mic ko 16k me badalne ke liye (koi install nahi chahiye)
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import INSTRUCTION as instruction
from youtube_control import handle_youtube_command

load_dotenv()

# Audio Settings (Gemini ke requirements ke mutabik)
MIC_RATE   = 16_000   # Gemini ko bhejne wali rate (standard PCM)
MIC_NATIVE = 48_000   # Mic hardware ki asli rate - isi par kholo (16k par seedha
                      # kholne se Windows silence pakdata hai, isliye software resample)
SPK_RATE   = 24_000   # Speaker output rate (Gemini 24kHz output deta hai)
CHUNK_SIZE = 320      # 20ms audio chunks (16000 * 0.02 = 320 frames)
NATIVE_CHUNK = 960    # 20ms @48k mono (48000 * 0.02)

async def run():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: .env file mein GOOGLE_API_KEY set karein!")
        return

    stop_event = asyncio.Event()

    # PyAudio ko initialize karein aur streams open karein
    # Sahi mic chuno: WASAPI wala asli mic, 48k native par kholo.
    # (Pehle "Primary Sound Capture Driver" pakadta tha + 16k par khulta tha = silence.)
    p = pyaudio.PyAudio()
    try:
        _def_in = p.get_default_input_device_info()
        _def_idx, _def_name = _def_in["index"], _def_in["name"].lower()
    except Exception:
        _def_idx, _def_name = None, ""
    _fam = ""
    for _k in ("microphone array", "microphone", "mic", "array", "headset"):
        if _k in _def_name:
            _fam = _k
            break
    _ranked = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] <= 0:
            continue
        try:
            _host = p.get_host_api_info_by_index(info["hostApi"])["name"]
        except Exception:
            _host = ""
        _nm, _ln = info["name"], info["name"].lower()
        if "stereo mix" in _ln or "pc speaker" in _ln or _ln.strip() == "input ()":
            continue
        _score = 0
        if "WASAPI" in _host:
            _score += 50
        elif "DirectSound" in _host:
            _score += 10
        elif "WDM-KS" in _host:
            _score -= 10
        if any(_k in _ln for _k in ("microphone", "mic", "array")):
            _score += 20
        elif "headset" in _ln:
            _score += 5
        if _fam and _fam in _ln:
            _score += 25
        if i == _def_idx:
            _score += 15
        if "hands-free" in _ln or "bthhfenum" in _ln:
            _score -= 30
        _ranked.append((_score, i, _nm, _host))
    _ranked.sort(key=lambda c: (-c[0], c[1]))
    if not _ranked:
        _ranked = [(0, None, "default", "")]
    # Har candidate par 48k try karo - jo pehle khule wahi mic
    mic_stream, mic_index, _16k_fallback = None, _ranked[0][1], False
    for _, _idx, _nm, _host in _ranked:
        try:
            mic_stream = p.open(
                format=pyaudio.paInt16, channels=1, rate=MIC_NATIVE,
                input=True, input_device_index=_idx, frames_per_buffer=NATIVE_CHUNK)
            mic_index = _idx
            break
        except Exception:
            continue
    if mic_stream is None:  # koi 48k na de toh 16k fallback
        _idx = _ranked[0][1]
        mic_stream = p.open(
            format=pyaudio.paInt16, channels=1, rate=MIC_RATE,
            input=True, input_device_index=_idx, frames_per_buffer=CHUNK_SIZE)
        mic_index, _16k_fallback = _idx, True
    if mic_index is not None:
        print(f"Mic device: {p.get_device_info_by_index(mic_index)['name']} (index {mic_index})")
    else:
        print("Mic device: default")
    # Mic check: 3 second bolo, level na aaye toh Windows mic volume dekho
    print("Mic check: 3 second me kuch bolo (jaise 'hello testing')...")
    _pks = []
    for _ in range(150):
        try:
            _d = mic_stream.read(NATIVE_CHUNK if not _16k_fallback else CHUNK_SIZE, False)
            _a = array.array("h"); _a.frombytes(_d)
            _pks.append(max(abs(x) for x in _a))
        except Exception:
            continue
    if _pks and max(_pks) < 500:
        print("Mic bahut quiet hai! Windows Settings - Sound - Input me mic volume 100 karo.")
    spk_stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SPK_RATE,
        output=True
    )

    speaker_queue = asyncio.Queue()
    speaker_playing = False

    # Speaker loop: Speaker queue se audio lekar play karta hai
    # NOTE: reconnect ke dauraan bhi chalta rehta hai (app-level, session se independent)
    async def play_loop():
        nonlocal speaker_playing
        while True:
            chunk = await speaker_queue.get()
            speaker_playing = True
            try:
                await asyncio.to_thread(spk_stream.write, chunk)
            except Exception as e:
                print(f"[speaker] error: {e!r}")
            speaker_queue.task_done()
            if speaker_queue.empty():
                speaker_playing = False

    # Gemini client aur configurations
    client = genai.Client(api_key=api_key)
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Laomedeia")
            )
        ),
        system_instruction=types.Content(parts=[types.Part(text=instruction)]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # VAD: dheere bolne par turn na kate - lamba silence wait (1500ms) + prefix.
        # (Pehle 300ms me kat jata tha, slow speech ke pause me turn toot jata tha.)
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                prefix_padding_ms=500,
                silence_duration_ms=1500,
            )
        ),
        # session_resumption disable rakha - Developer API pe handle restore
        # reliable nahi chalta (transparent sirf Enterprise mode me hai)
    )

    # Reconnect ke liye shared state
    current_session = None      # active session (None = disconnected)

    # Text loop: User type karke message bhej sake
    # NOTE: ye session se independent hai, current_session reference use karta hai
    # taaki reconnect ke baad bhi bina restart ke chalta rahe
    async def text_loop():
        nonlocal current_session
        input_warned = False
        while True:
            try:
                line = await asyncio.to_thread(input)
                input_warned = False
            except KeyboardInterrupt:
                # Ctrl+C ne read tod diya - signal handler already mode switch kar chuka hai
                continue
            except BaseException:
                # Ctrl+C/OSError se read abort ho sakta hai - text_loop kabhi na mare,
                # warna app band ho jayega. Thodi der baad dobara try.
                if not input_warned:
                    print("[text] input padhne me dikkat - 0.3s me dobara try karunga")
                    input_warned = True
                await asyncio.sleep(0.3)
                continue
            line = line.strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit"):
                print("Jarvis band ho raha hai... Alvida!")
                stop_event.set()
                return
            if MODE != "text":
                print("⌨️ Mic mode ho - text bhejne ke liye pehle Ctrl+C dabayein (text mode).")
                continue
            print(f"⌨️ You: {line}")
            # YouTube command ho (open / gana) toh pehle locally action lo,
            # phir Maya ko batao taaki wo pyaar se confirm kare.
            try:
                # Network search me second lag sakte hain - thread me chalao taaki voice loop na ruke
                _ok, _msg = await asyncio.to_thread(handle_youtube_command, line)
            except Exception as _e:
                _ok, _msg = False, ""
            if _ok:
                print(f"[YouTube] {_msg}")
                line = line + f"\n[System note: Maine locally action le liya hai - {_msg}. User ko pyaar se confirm karo ki kaam ho gaya.]"
            # Reconnect ho raha ho toh wait karein
            while current_session is None:
                await asyncio.sleep(0.3)
            try:
                await current_session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(text=line)]
                    ),
                    turn_complete=True,
                )
            except Exception as e:
                print(f"[text] send failed: {e!r}")

    # Mic pipeline: reader mic padhta rehta hai, sender 100ms batch me bhejta hai.
    # (Pehle har 20ms par alag send hota tha - network RTT se aadhi speed par pahunchta
    #  tha aur awaaz slow-motion lagti thi. Batch me realtime speed milti hai.)
    mic_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def mic_reader():
        _rs = None
        _cn = NATIVE_CHUNK if not _16k_fallback else CHUNK_SIZE
        while True:
            try:
                data = await asyncio.to_thread(mic_stream.read, _cn, False)
            except Exception:
                continue
            if MODE != "mic":
                _rs = None
                continue
            if not _16k_fallback:
                try:
                    data, _rs = audioop.ratecv(data, 2, 1, MIC_NATIVE, MIC_RATE, _rs)
                except Exception:
                    continue
            try:
                mic_queue.put_nowait(data)
            except asyncio.QueueFull:
                try:
                    mic_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    mic_queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass

    # Mic loop: Mic se data lekar Gemini ko bhejta hai
    async def send_loop():
        nonlocal current_session
        while True:
            try:
                first = await mic_queue.get()
            except asyncio.CancelledError:
                break
            batch = [first]
            while len(batch) < 5:
                try:
                    batch.append(mic_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            _wait = time.monotonic() + 0.08
            while len(batch) < 5 and time.monotonic() < _wait:
                try:
                    batch.append(await asyncio.wait_for(mic_queue.get(), timeout=0.02))
                except asyncio.TimeoutError:
                    pass
            data = b"".join(batch)
            # Dheemi awaaz ke liye auto-gain (max 24x), pure noise (<60) ko haath nahi
            a = array.array("h"); a.frombytes(data)
            peak = max(abs(x) for x in a)
            if 60 <= peak < 15000:
                data = audioop.mul(data, 2, min(15000 / peak, 24.0))
            elif peak > 20000:
                # Mic signal bahut hot hai (peak 32768 clipping) - sirf jab clip ho tab gain cut karein
                scale = 20000 / peak
                data = array.array("h", (int(x * scale) for x in a)).tobytes()
            # Disconnected ho toh skip karein, warna bhejne ki koshish karein
            # (speaker chalte hue bhi bhejo taaki beech me tok sako)
            if current_session is None:
                continue
            try:
                await current_session.send_realtime_input(
                    audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                )
            except asyncio.CancelledError:
                break
            except Exception:
                # Connection toot chuki hai - connection_manager reconnect karega
                await asyncio.sleep(0.5)

    # Receive loop: Gemini se responses aur transcripts leta hai
    # NOTE: SDK ka session.receive() generator har turn_complete ke baad
    # khud break ho jata hai, isliye har turn ke baad use restart karna
    # padta hai warna dusre/tisre message ka response kabhi sunne wala nahi hota.
    async def receive_loop(session):
        user_buf, model_buf = [], []
        while True:
            try:
                async for response in session.receive():
                    sc = response.server_content
                    if not sc:
                        continue

                    # Agar audio model response hai, toh use speaker queue me daalein
                    if sc.model_turn:
                        for part in sc.model_turn.parts or []:
                            if part.inline_data:
                                speaker_queue.put_nowait(part.inline_data.data)

                    # Transcriptions collect karein
                    if sc.input_transcription:
                        t = sc.input_transcription.text.strip()
                        if t: user_buf.append(t)

                    if sc.output_transcription:
                        t = sc.output_transcription.text.strip()
                        if t: model_buf.append(t)

                    # Turn complete hone par console par print karein
                    if sc.turn_complete:
                        if user_buf:
                            _user_text = ' '.join(user_buf)
                            print(f"👤 User: {_user_text}")
                            # Mic se YouTube command aaya ho toh turant action lo
                            try:
                                # Network search me second lag sakte hain - thread me chalao taaki voice loop na ruke
                                _ok, _msg = await asyncio.to_thread(handle_youtube_command, _user_text)
                            except Exception:
                                _ok, _msg = False, ""
                            if _ok:
                                print(f"[YouTube] {_msg}")
                                try:
                                    await session.send_client_content(
                                        turns=types.Content(
                                            role="user",
                                            parts=[types.Part(
                                                text=f"[System note: User ne bola '{_user_text}'. "
                                                     f"Maine locally action le liya hai - {_msg}. "
                                                     f"Ab user ko pyaar se confirm karo ki kaam ho gaya.]"
                                            )]
                                        ),
                                        turn_complete=True,
                                    )
                                except Exception as _e:
                                    print(f"[youtube] maya ko batane me dikkat: {_e!r}")
                            user_buf.clear()
                        if model_buf:
                            print(f"🤖 Jarvis: {' '.join(model_buf)}")
                            model_buf.clear()
                        # Generator yahin break ho chuka hoga, agla
                        # turn lene ke liye bahar se dobara receive() call hoga
            except Exception as e:
                print(f"[receive] connection error: {e!r}")
                break

    # Connection manager: connect, run till death, auto-reconnect
    async def connection_manager():
        nonlocal current_session
        while True:
            try:
                print("\nJarvis (Gemini Live) se connect ho raha hai...")
                async with client.aio.live.connect(
                    model="gemini-3.1-flash-live-preview",
                    config=config
                ) as session:
                    current_session = session
                    print("Connected! Mic mode chalu - boliye | Text: Ctrl+C | Band: 'exit'\n")
                    # Receive tab tak chalega jab tak connection zinda hai
                    await receive_loop(session)
            except Exception as e:
                print(f"[connect] error: {e!r}")
            # Yahan connection mar chuka hai (ya connect hi nahi hua)
            current_session = None
            print("Connection lost. 3 sec me dobara connect kar raha hoon...")
            await asyncio.sleep(3)

    # Sabhi loops parallel me - default MICROPHONE mode, Ctrl+C se text toggle
    print("MIC default chalu hai - seedha boliye. Text: Ctrl+C | Band: 'exit' likhein.\n")
    tasks = [
        asyncio.create_task(play_loop()),
        asyncio.create_task(mic_reader()),
        asyncio.create_task(send_loop()),
        asyncio.create_task(text_loop()),
        asyncio.create_task(connection_manager()),
    ]
    stop_task = asyncio.create_task(stop_event.wait())
    try:
        # 'exit'/'quit' likhne tak intezaar. Stray KeyboardInterrupt aaye toh ignore -
        # Ctrl+C ka kaam signal handler dekh raha hai, app ko band nahi hona chahiye.
        while True:
            try:
                await asyncio.wait([*tasks, stop_task], return_when=asyncio.FIRST_COMPLETED)
                break
            except KeyboardInterrupt:
                continue
    finally:
        # Pehle sabhi loops cancel karein, phir streams band karein
        stop_task.cancel()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, stop_task, return_exceptions=True)
        # Cleanup: Sabhi streams aur PyAudio ko properly close karein
        print("\nCleaning up audio resources...")
        mic_stream.stop_stream()
        mic_stream.close()
        spk_stream.stop_stream()
        spk_stream.close()
        p.terminate()
        print("Done!")
    # Kisi loop ki exception rahi ho toh dikhao
    for t in tasks:
        if not t.cancelled() and t.exception() is not None:
            raise t.exception()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nJarvis Stopped. Alvida!")
