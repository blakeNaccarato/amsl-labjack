<#.SYNOPSIS
Initialize repository.#>

git init

# ? Modify GitHub repo later on only if there were not already commits in this repo
try { git rev-parse HEAD }
catch [System.Management.Automation.NativeCommandExitException] { $Fresh = $True }

git add .
try { git commit --no-verify -m 'Prepare template using blakeNaccarato/copier-python' }
catch [System.Management.Automation.NativeCommandExitException] {}

git submodule add --force --name 'typings' 'https://github.com/softboiler/python-type-stubs.git' 'typings'
git add .
try { git commit --no-verify -m 'Add template and type stub submodules' }
catch [System.Management.Automation.NativeCommandExitException] {}

Initialize-Shell

git add .
try { git commit --no-verify -m 'Lock' }
catch [System.Management.Automation.NativeCommandExitException] {}

# ? Modify GitHub repo if there were not already commits in this repo
if ($Fresh) {
    if ( !(git remote) ) {
        git remote add origin 'https://github.com/blakeNaccarato/amsl-labjack.git'
        git branch --move --force main
    }
    gh repo edit --description (
        Get-Content '.copier-answers.yml' |
            Find-Pattern '^project_description:\s(.+)$'
    )
    gh repo edit --homepage 'https://blakeNaccarato.github.io/amsl-labjack/'
}

git push --set-upstream origin main
