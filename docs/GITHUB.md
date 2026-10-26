# Publish to GitHub

This folder is the public source edition. Keep it separate from personal installations, downloaded audio and development/research artifacts.

## Using the website

1. Extract `SesKutusu-GitHub.zip`.
2. Open [New repository](https://github.com/new), choose your account, enter `SesKutusu` and select the intended visibility.
3. Leave GitHub's automatic README, license and gitignore options disabled; this project already includes those files.
4. Use **Add file → Upload files** to upload the project contents. `README.md` and `LICENSE` belong at the repository root. Include the hidden `.github` folder and `.gitignore` file.
5. Commit the files and inspect the Windows test result under **Actions**.
6. Optionally pin the repository on your GitHub profile.

GitHub Desktop is another way to publish this folder. Exclude personal `data/` directories and existing EXE/DLL bundles.

## Using Git

Create an empty repository in your account, then run these commands from the extracted project root:

```powershell
git init -b main
git add .
git diff --cached --stat
git commit -m "Initial public source release"
git remote add origin https://github.com/YOUR_USERNAME/SesKutusu.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub login. Inspect the staged file list before committing to ensure no personal files are included.

The application defaults to English. Other interface languages are optional settings; repository documentation, examples and initial library names use English.
