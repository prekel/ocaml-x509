"""Check OpenSSL interoperability and the actual attributes inside PKCS12 bags."""
import re


def verify(stage, prefix, suite, run):
    fixtures = stage / "fixtures"
    fixtures.mkdir()
    for stem, subject in (("cert", "/CN=overlay-leaf"), ("ca", "/CN=overlay-ca")):
        key = "key" if stem == "cert" else "ca-key"
        run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-days", "2", "-subj", subject, "-keyout", fixtures / f"{key}.pem",
            "-out", fixtures / f"{stem}.pem", cwd=stage, show=False)
    run(*prefix, "dune", "exec", "--profile", "release", "./overlay_check/check.exe", cwd=stage)
    explicit = (fixtures / "expected-id").read_bytes().hex()
    assert len(bytes.fromhex(explicit)) == 20
    fingerprint = run("openssl", "x509", "-in", fixtures / "cert.pem", "-noout",
                      "-fingerprint", "-sha1", cwd=stage, show=False)
    assert fingerprint.strip().split("=")[-1].replace(":", "").lower() == explicit
    default = (fixtures / "default-id").read_bytes().hex()
    for name in ("explicit", "default", "chain-explicit", "chain-default"):
        data = run("openssl", "pkcs12", "-in", fixtures / f"{name}.p12",
                   "-passin", "pass:overlay-test", "-nodes", "-info", cwd=stage, show=False)
        ids = [value.replace(" ", "").lower() for value in re.findall(r"localKeyID: ([0-9A-Fa-f ]+)", data)]
        count = 2 if suite == "latest" or not name.startswith("chain-") else 3
        expected = explicit if name.endswith("explicit") else default
        if suite == "legacy" and name.endswith("default"):
            count = 0
        assert ids == [expected] * count, (name, ids, expected)
        assert data.count("BEGIN CERTIFICATE") == (2 if name.startswith("chain-") else 1)
        assert data.count("BEGIN PRIVATE KEY") == 1
        if name.startswith("chain-") and suite == "latest":
            bags = data.split("Bag Attributes")
            ca = [bag for bag in bags if "subject=CN=overlay-ca" in bag or "subject=CN = overlay-ca" in bag]
            assert len(ca) == 1 and "localKeyID" not in ca[0]
    print("OpenSSL: MAC, extraction, explicit/default localKeyID and CA attributes passed")
