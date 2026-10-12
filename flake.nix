{
  description = "Monaspace Argon (upright) + Radon (italic) merged into one font family";

  inputs = {
    nixpkgs = {
      url = "github:NixOS/nixpkgs/nixos-unstable";
    };
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);

      mkPackage =
        {
          lib,
          stdenvNoCC,
          python3,
          monaspace,
          pname,
          uprightPrefix, # file prefix of the upright family (Regular/Bold)
          italicPrefix, # file prefix of the italic family (Italic/Bold Italic)
          familyName,
        }:
        let

          fontDirs = lib.concatMapStringsSep " " (o: "${monaspace.${o}}") (monaspace.outputs or [ "out" ]);
        in
        stdenvNoCC.mkDerivation {
          inherit pname;
          inherit (monaspace) version;

          dontUnpack = true;
          nativeBuildInputs = [ (python3.withPackages (ps: [ ps.fonttools ])) ];

          buildPhase = ''
            runHook preBuild
            python3 ${./main.py} build "${familyName}" "${uprightPrefix}" "${italicPrefix}" ${fontDirs}
            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall
            mkdir -p $out/share/fonts/opentype
            cp build/* $out/share/fonts/opentype/
            runHook postInstall
          '';

          meta = {
            description = "Monaspace Argon + Radon italics merged into one family (${familyName})";
            homepage = "https://monaspace.githubnext.com/";
            license = lib.licenses.ofl;
            platforms = lib.platforms.all;
          };
        };

      # Uses the consumer's own pkgs (final.*), so their nixpkgs version and any
      # overrides carry through automatically.
      overlay = final: prev: {
        # Nerd Font build shipped inside nixpkgs' monaspace (MonaspaceArgonNF-*.otf).
        monaspace-script-nerd = final.callPackage mkPackage {
          pname = "monaspace-script-nerd";
          uprightPrefix = "MonaspaceArgonNF";
          italicPrefix = "MonaspaceRadonNF";
          familyName = "Scripted Monaspace NF";
        };

        # Plain build, no Nerd Font glyph patching.
        monaspace-script = final.callPackage mkPackage {
          pname = "monaspace-script";
          uprightPrefix = "MonaspaceArgon";
          italicPrefix = "MonaspaceRadon";
          familyName = "Scripted Monaspace";
        };

        monaspace-script-all = final.symlinkJoin {
          name = "monaspace-script-all";
          paths = [
            final.monaspace-script
            final.monaspace-script-nerd
          ];
        };
      };
    in
    {
      overlays.default = overlay;

      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ overlay ];
          };
        in
        {
          inherit (pkgs) monaspace-script monaspace-script-nerd monaspace-script-all;
          default = pkgs.monaspace-script-all;
        }
      );
    };
}
