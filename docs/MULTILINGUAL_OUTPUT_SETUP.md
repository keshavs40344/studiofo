# Multilingual outputs and voice-model licensing

UPSC Studio can create translated scripts and subtitle sidecars through either a local LibreTranslate server or optional offline Argos Translate models. It does not silently substitute an English voice for another language.

## 1. Translation provider

Choose one:

- **Local LibreTranslate:** set `UPSC_STUDIO_TRANSLATE_URL` to the local server URL (default `http://127.0.0.1:5000`). Set `UPSC_STUDIO_TRANSLATE_API_KEY` only when the server requires it.
- **Offline Argos Translate:** install the optional dependency with `pip install -e ".[i18n]"`, then install the relevant Argos language packages. The source language defaults to English for Argos; configure `UPSC_STUDIO_TRANSLATE_SOURCE_LANG` for another supported source code.

The dashboard checks the provider's supported language list. The catalogue contains English, Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi and Odia, but a language is offered by a provider only when that provider reports it as available.

Machine translation is a draft. A fluent human reviewer must check meaning, legal terminology, names, dates, pronunciation spellings and subtitle line breaks before release.

## 2. Install a Piper voice model

Place the target-language Piper files in:

`data/tts_models/piper/`

For a model such as `ta_IN-example-medium.onnx`, the matching `ta_IN-example-medium.onnx.json` config file must also be present. The runtime checks the locale prefix in the model filename against the requested language code.

Do not infer a model's licence from its filename or from the fact that it can be downloaded. After checking the exact model's licence and commercial-use terms, create `data/tts_models/piper/voice_licenses.json`:

```json
{
  "ta_IN-example-medium.onnx": {
    "license": "EXACT-LICENSE-NAME",
    "attribution": "COPY THE MODEL AUTHOR'S REQUIRED ATTRIBUTION",
    "commercial_use": true,
    "confirmed_by": "REVIEWER NAME"
  }
}
```

Use the exact model filename as the key. The runtime will not synthesize a dubbed voice unless the config file and all four licence fields are present. Set `commercial_use` to true only when the exact model licence permits the intended use. This manifest records a human licence review; it is not an independent legal determination.

The isolated Piper runtime expected by the current application is `.venv_tts/Scripts/python.exe` on Windows. It must have a compatible Piper package installed.

## 3. Generate a language version

1. Run the base production workflow and create the storyboard.
2. Configure the translation provider and install the language package/model.
3. Open the project dashboard and select the target language under **Multilingual Script, Subtitles & Dub**.
4. Generate the translated script and SRT.
5. If a compatible licensed Piper model is installed, the workflow also creates translated narration and a separate dubbed MP4 reusing the base documentary picture.
6. Review the translated script, voice naturalness, pronunciation, subtitle sync and dubbed playback. The sidecar SRT is not burned into the MP4.
7. Complete a fresh human release review before publishing. A language output is not automatically approved because it rendered.

## 4. Output files

- `teaching/translations/<language>/translated_script.md`
- `subtitles/<language>/subtitles.srt`
- `audio/multilingual/<language>/narration.wav` (only when a licensed Piper model is available)
- `audio/multilingual/<language>/voice_quality_report.json`
- `render/languages/<language>/documentary_<language>.mp4` (only when translated audio and the base video are available)
- `render/languages/<language>/language_output_manifest.json`

If no provider or target-language voice model is configured, the dashboard returns an explicit blocked/translation-only status. It does not label the output dubbed.
