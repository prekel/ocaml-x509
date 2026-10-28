let of_string = Cstruct.of_string
let to_string = Cstruct.to_string
let initialize () = Mirage_crypto_rng_unix.initialize (module Mirage_crypto_rng.Fortuna)
