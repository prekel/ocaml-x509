let ok = function Ok x -> x | Error (`Msg m) -> failwith m
let read path =
  let ic = open_in_bin path in
  let data = really_input_string ic (in_channel_length ic) in
  close_in ic;
  Compat.of_string data
let write path data =
  let oc = open_out_bin path in
  output_string oc (Compat.to_string data);
  close_out oc

let () =
  Compat.initialize ();
  let open X509 in
  let cert = ok (Certificate.decode_pem (read "fixtures/cert.pem")) in
  let ca = ok (Certificate.decode_pem (read "fixtures/ca.pem")) in
  let key = ok (Private_key.decode_pem (read "fixtures/key.pem")) in
  let id = Certificate.fingerprint `SHA1 cert in
  write "fixtures/expected-id" id;
  write "fixtures/default-id" (Public_key.fingerprint (Private_key.public key));
  List.iter (fun (name, local_key_id, certificates) ->
      let p12 = PKCS12.create ?local_key_id "overlay-test" certificates key in
      let encoded = PKCS12.encode_der p12 in
      let decoded = ok (PKCS12.decode_der encoded) in
      let bags = ok (PKCS12.verify "overlay-test" decoded) in
      let certs = List.filter_map (function `Certificate c -> Some c | _ -> None) bags in
      assert (List.length certs = List.length certificates);
      List.iter (fun cert ->
          assert (List.exists (fun candidate ->
              Compat.to_string (Certificate.fingerprint `SHA1 candidate) =
              Compat.to_string (Certificate.fingerprint `SHA1 cert)) certs)) certificates;
      let keys = List.filter_map (function
          | `Private_key k | `Decrypted_private_key k -> Some k | _ -> None) bags in
      assert (List.length keys = 1);
      assert (Compat.to_string (Public_key.fingerprint (Private_key.public (List.hd keys))) =
              Compat.to_string (Public_key.fingerprint (Private_key.public key)));
      assert (Result.is_error (PKCS12.verify "wrong-password" decoded));
      write ("fixtures/" ^ name ^ ".p12") encoded)
    [ "explicit", Some id, [cert];
      "default", None, [cert];
      "chain-explicit", Some id, [cert; ca];
      "chain-default", None, [cert; ca] ];
  print_endline "PKCS12 round trips and wrong-password checks passed"
