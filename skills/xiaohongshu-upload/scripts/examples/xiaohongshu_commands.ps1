# PowerShell examples for the installed mpau CLI.

# account_name is user-defined. One account_name maps to one account file.
# You can prepare multiple account names and run them in parallel.
$account = "account_a"
$video = "videos/demo.mp4"
$thumbnail = "videos/demo.png"
$noteImages = @("videos/1.png", "videos/2.png")

mpau xiaohongshu login --account $account --headless
mpau xiaohongshu check --account $account

mpau xiaohongshu upload-video `
  --account $account `
  --file $video `
  --title "Xiaohongshu video from PowerShell" `
  --desc "Xiaohongshu video description from PowerShell" `
  --tags "cli,video" `
  --thumbnail $thumbnail `
  --headless

mpau xiaohongshu upload-note `
  --account $account `
  --images $noteImages `
  --title "Xiaohongshu note title from PowerShell" `
  --note "Xiaohongshu note from PowerShell" `
  --tags "cli,note" `
  --headless
