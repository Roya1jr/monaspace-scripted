# Scripted Mona

A Nix flake that merges two Monaspace font-families into one:
- Monaspace Argon for regular and bold text 
- Monaspace Radon for italic and italic bold text

Inspired by MonoLisa & Victor Mono this allows marking of comments and keywords as italic in your code editor while everthing else stays regular.
This flake contains no fonts, it build them locally from the monaspace package in your own nixpkgs so the result tracks the MonaSpace version in your nixpkgs

## Packages

| Package               | Font-Family Name      | Notes             |
| --------------------- | --------------------- | ----------------- |
| monaspace-script      | Scripted MonaSpace    | Regular MonaSpace |
| monaspace-script-nerd | Scripted MonaSpace NF | NerdFont Variant  |
They use different file names so you can pick either in your editor

## Usage

Add the flakes as inputs and apply the overlay

```nix
inputs = {
	monaspace-script = {
		url = "github:Roya1jr/monaspace-scripted";
	    inputs.nixpkgs.follows = "nixpkgs";
	}
}
```

Build the locally to test 

```sh
git clone https://github.com/Roya1jr/monaspace-scripted.git
cd monaspace-scripted
nix build
```

this will create a result folder link to the nix store and you can copy the generated font files from there

## License
[MIT](./LICENSE)
