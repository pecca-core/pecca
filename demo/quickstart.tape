# Pecca quickstart GIF. Regenerate: `vhs demo/quickstart.tape` from the repo root (needs vhs, ttyd, ffmpeg).
Output docs/assets/quickstart.gif
Output docs/assets/quickstart.mp4

Set Shell "bash"
Set Theme "Catppuccin Mocha"
Set FontSize 16
Set Width 1200
Set Height 640
Set TypingSpeed 40ms
Set Padding 20
Set Framerate 20
Set PlaybackSpeed 1.5
Set WaitPattern /\$$/
Set WaitTimeout 120s

Hide
Type "source demo/env.sh" Enter
Sleep 90s
Show

# 1. install (simulated: pecca is pre-installed in the recording environment)
Type "pip install pecca" Enter
Wait
Sleep 1s

# 2. demo data
Type "pecca datasets demo" Enter
Wait
Sleep 1.5s

# 3. project
Type "pecca init --profile none" Enter
Wait
Sleep 1.5s

# 4. profile
Hide
Type "clear" Enter
Show
Type "pecca profile" Enter
Wait
Sleep 3s

# 5. train
Hide
Type "clear" Enter
Show
Type "pecca train default/default/route_rfi --candidates tfidf_linear,e5_logreg" Enter
Wait
Sleep 3.5s

# 6. shadow
Hide
Type "clear" Enter
Show
Type "pecca promote default/default/route_rfi --mode shadow" Enter
Wait
Sleep 1s

# 7. status
Type "pecca status default/default/route_rfi" Enter
Wait
Sleep 3s

# 8. result (simulated summary line)
Type "echo 'LLM calls on routing: 100% -> 0% expected fallback (synthetic data)'" Enter
Wait
Sleep 3s
