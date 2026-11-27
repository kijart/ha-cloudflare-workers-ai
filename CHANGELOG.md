# Changelog

## 0.1.0 (2026-11-27)


### Features

* add diagnostics and retired model repair issue ([4ab2159](https://github.com/kijart/ha-cloudflare-workers-ai/commit/4ab2159e8999c7379e7e1ba15ee211949a0a1384))
* add integration brand icons ([073d0c2](https://github.com/kijart/ha-cloudflare-workers-ai/commit/073d0c283e9630df80f736ae8e1ae1538c331203))
* **api:** add minimal Workers AI HTTP client ([745e86a](https://github.com/kijart/ha-cloudflare-workers-ai/commit/745e86a0e33f499849d84c03b2c3e6f31b4c264d))
* **config_flow:** add account setup and entry lifecycle ([14aa292](https://github.com/kijart/ha-cloudflare-workers-ai/commit/14aa292c02381d88e09dab6ba456c06b79ba9895))
* **config_flow:** add model, voice and prompt options ([9a7769c](https://github.com/kijart/ha-cloudflare-workers-ai/commit/9a7769c77830cf8a8da34b7643c1ccbdabbec2a7))
* **config_flow:** add reauth and reconfigure ([734a536](https://github.com/kijart/ha-cloudflare-workers-ai/commit/734a536f770e5bb4249aadba2a492f8eb0343d49))
* declare parallel updates for STT and TTS ([adb9a0a](https://github.com/kijart/ha-cloudflare-workers-ai/commit/adb9a0ac96fdeb359345b6708318c618c86f846e))
* **models:** discover Whisper and Aura models ([9a18938](https://github.com/kijart/ha-cloudflare-workers-ai/commit/9a18938bc8f67348d07e40fadc48ddadce8968f7))
* **stt:** add Whisper speech-to-text entity ([3e749ef](https://github.com/kijart/ha-cloudflare-workers-ai/commit/3e749ef1244eba011d5932e1250e24a8afa0790b))
* **tts:** add Aura text-to-speech entity ([e67ee28](https://github.com/kijart/ha-cloudflare-workers-ai/commit/e67ee28528977347575fb3bff8101b14c7cec1c0))


### Bug Fixes

* **api:** send gateway token only to gateway requests ([32adbbc](https://github.com/kijart/ha-cloudflare-workers-ai/commit/32adbbc7edc4081a028fe77b09f29c162627b7f9))
* **api:** stop reauth loop on AI Gateway auth errors ([d494e57](https://github.com/kijart/ha-cloudflare-workers-ai/commit/d494e57b7997c2d7a6e3a16be67d3c28a9c133e2))
* **config_flow:** offer voices of the selected TTS model ([6b3281d](https://github.com/kijart/ha-cloudflare-workers-ai/commit/6b3281d5805e40e6e0e17f4d5d3b46fd40f02c39))
* **config_flow:** replace entry data on reconfigure ([1b57925](https://github.com/kijart/ha-cloudflare-workers-ai/commit/1b5792522aebd1d7d3eb5af5be9705e6ca340d74))
* **models:** fall back when discovery finds no usable models ([bf4dff9](https://github.com/kijart/ha-cloudflare-workers-ai/commit/bf4dff95fa0571bdc84b2fb79cfca99fbf45e195))
* **models:** keep listed models when schema lookup fails ([99e2019](https://github.com/kijart/ha-cloudflare-workers-ai/commit/99e201935850e856e5a4bc770fe2a70957b6f38c))
* **models:** limit Whisper family to base64 input models ([5b06a11](https://github.com/kijart/ha-cloudflare-workers-ai/commit/5b06a1192f8ddea2c9b3689fb2b0692af8cb94fc))
* nest entity name translations under their translation key ([4a0450c](https://github.com/kijart/ha-cloudflare-workers-ai/commit/4a0450c520f744afb169908ac59073f66cff8f9b))
* **tts:** include configured voice in default options ([58f80a8](https://github.com/kijart/ha-cloudflare-workers-ai/commit/58f80a8fb026a94693199fe9b5037ae6b1a342a0))
