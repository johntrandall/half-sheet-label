# Canonical source of the formula. At release, copy this into the tap repo
# (johntrandall/homebrew-tap Formula/) with the real release-tarball sha256.
#
#   1. gh release create v0.1.0 ...
#   2. curl -sL <tarball> | shasum -a 256   -> fill `sha256` below
#   3. cp Formula/half-sheet-label.rb into the tap clone, commit, push
#   4. brew style / brew audit --strict / brew install johntrandall/tap/half-sheet-label
class HalfSheetLabel < Formula
  include Language::Python::Virtualenv

  desc "Impose a rendered label PDF onto half-sheet 2-up stock and print it"
  homepage "https://github.com/johntrandall/half-sheet-label"
  url "https://github.com/johntrandall/half-sheet-label/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # TODO: fill at release
  license "MIT"
  head "https://github.com/johntrandall/half-sheet-label.git", branch: "main"

  depends_on :macos # prints via CUPS `lp`, previews via `open -a Preview`
  depends_on "python@3.13"

  resource "pypdf" do
    url "https://files.pythonhosted.org/packages/1a/7f/5bc369dedae6750e23fc9ce82f6396258f92ed80ae0137732738a6d4ffce/pypdf-6.16.0.tar.gz"
    sha256 "dfc5b0afeb5e02e9ee1dce71c09071f062d1a4030d2925f03a5daee0ee975ed8"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "half-sheet-label", shell_output("#{bin}/half-sheet-label --version")
  end
end
