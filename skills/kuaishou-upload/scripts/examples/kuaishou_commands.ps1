# PowerShell examples for the installed mpau CLI.

# account_name is user-defined. One account_name maps to one account file.
# You can prepare multiple account names and run them in parallel.
$account = "account_a"
$video = "videos/demo.mp4"
$thumbnail = "videos/demo.png"
$noteImages = @("videos/1.png", "videos/2.png", "videos/3.png")

mpau kuaishou login --account $account
mpau kuaishou check --account $account

mpau kuaishou upload-video `
  --account $account `
  --file $video `
  --title "Kuaishou video from PowerShell" `
  --desc "Kuaishou video description from PowerShell" `
  --tags "cli,video" `
  --thumbnail $thumbnail `
  --headless

mpau kuaishou upload-note `
  --account $account `
  --images $noteImages `
  --title "Kuaishou note title from PowerShell" `
  --note "Kuaishou note from PowerShell" `
  --tags "cli,note" `
  --headless
