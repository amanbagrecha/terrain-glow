# Login state

When FusedRender is not signed in to Fused, or the sign-in is out of date, the app shows a short card: "Sign in to Fused",
one line of text and one button. It never shows a traceback or a terminal command.

## Sub-features

- `login-card` the card: title "Sign in to Fused", the text "Terrain Glow gets the terrain data with your Fused account.", the button Sign in.
- `login-sign-in` Sign in starts the Fused sign-in in the browser (`POST /api/canvases/login`, the same call as the FusedRender shell).
  The card shows "Complete the sign-in in your browser.", a progress bar and Cancel.
- `login-return` the page reads `/api/canvases/status` every 2 s while the card shows (not while the page is hidden). When the
  credentials file is newer than the `creds_stamp` that `terrain.py` returned (any sign-in: this card, Canvases or a terminal), the
  toast shows "You are signed in to Fused." and the data loads with no other click. A cached login error starts again by itself
  when the credentials file is newer than the error.
- `login-keep` a change to the light, look or view while the card shows does not reload the card. A change to the area, while a
  sign-in runs, shows the card again with Cancel.
- `login-cancel` Cancel stops the sign-in (`POST /api/canvases/login/cancel`) and shows Sign in again.
- `login-not-complete` if the sign-in ends with no new credentials, the card shows "The sign-in did not complete. Try again."
- `login-not-start` if the sign-in call fails, the card shows "The sign-in did not start. Try again."
- `login-phone` on a phone (`fused.device` is not "desktop"), the card shows "Sign in to Fused on the computer that runs
  FusedRender." and Try again. The local-network listener does not allow `/api/canvases/*`, and a browser sign-in opens on the computer.

## How to get to it (user POV)

- Open the app while FusedRender is signed out of Fused, or while the sign-in is out of date.

## Driving it with tg

Preconditions:

- None. The stub answers inside the page only. The real login of this computer stays as it is.

Card and return (`login-card`, `login-sign-in`, `login-return`):

- `tg open "place=matterhorn" --stub login --sign-in-ms 4000`, `tg shot login-start`.
- `tg click "#signIn"`, `tg shot login-wait`. `tg eval "return W.document.getElementById('loadSub').textContent"` shows the wait text,
  and `tg eval "return W.__tgStub.loginCalls"` is 1 (the page sent the sign-in call once).
- `tg wait "!W.document.body.classList.contains('login')" --timeout 20`. The stub sign-in ends after 4 s, the toast shows
  "You are signed in to Fused." and the real data loads (`tg wait "!W.document.body.classList.contains('loading')"`).

Cancel and failures (`login-cancel`, `login-not-complete`, `login-not-start`):

- `tg open "place=matterhorn" --stub login --sign-in-ms -1`, `tg click "#signIn"`, `tg click "#loginCancel"`. The card shows Sign in.
- `tg click "#signIn"`, then `tg eval "W.__tgStub.inFlight = false; return 1"`. After 2 s the card shows "did not complete".
- `tg open "place=matterhorn" --stub login-fail`, `tg click "#signIn"`. The card shows "did not start".

Phone (`login-phone`):

- `tg --size 390x844 open "place=matterhorn" --stub login-phone`, `tg --size 390x844 shot login-phone`. Only Try again shows.

Real signed-out server (optional, slow):

- A second fused-render server with an empty HOME, so the real login is not touched:
  `HOME=<empty dir> /Applications/FusedRender.app/Contents/MacOS/python -m fused_render.cli --no-browser --port 1791 &`
- `FUSED_RENDER_ORIGIN=http://127.0.0.1:1791 tg launch --port 9413`, then `tg open "" --timeout 5` (it times out on purpose),
  then `tg wait "W.document.body.classList.contains('login')" --timeout 300` (the first open installs the app environment).

## Gotchas

- Do not click Sign in on a real signed-out server. It opens the Fused sign-in in the browser of this computer.
- The stub lives only in the current page. A reload (for example the auto-reload after an edit to index.html) or a `tg open`
  without `--stub` removes it. `tg click` and `tg touch` refuse Sign in when the stub is not there; `tg eval` has no guard.
- Stop a second server and its Chrome after the run (`tg cleanup`, then stop the server you started by its PID).
- Never move or edit the real `~/.fused/credentials`.
