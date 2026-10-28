let of_string s = s
let to_string s = s
let initialize () = Mirage_crypto_rng_unix.initialize (module Mirage_crypto_rng.Fortuna)
