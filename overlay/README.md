# X509: готовые пакеты для opam overlay

Два независимых каталога для копирования в `packages/x509/` вашего
overlay-репозитория. В каждом уже есть полный `opam`, официальный URL архива,
его checksum, `patches`, `extra-files` с SHA256 и `files/` с патчем.
Дописывать поля вручную не требуется.

| Каталог | Назначение |
| --- | --- |
| `packages/x509/x509.0.16.4` | Замена форка NightBlues на `a307dd319b2896789926b3a85cbd544ca6ef81d0` |
| `packages/x509/x509.1.2.0` | Обновление на релиз 1.2.0 с явным `local_key_id` |

## Копирование и установка

Из корня этого checkout:

```sh
overlay_repo=/path/to/corporate-opam-overlay
mkdir -p "$overlay_repo/packages/x509"
cp -R overlay/packages/x509/x509.0.16.4 "$overlay_repo/packages/x509/"
cp -R overlay/packages/x509/x509.1.2.0 "$overlay_repo/packages/x509/"
```

Далее в нужном switch обновить подключённый корпоративный репозиторий
(`corp-overlay` — его имя в `opam repository list`) и снять существующий git pin:

```sh
opam update corp-overlay
opam pin list
# Выполнить, если x509 закреплён за форком:
opam pin remove --no-action x509
opam install x509.0.16.4
```

Если та же версия уже установлена, выполнить `opam reinstall x509.0.16.4`,
чтобы гарантированно пересобрать её с патчем. Для обновления выбрать
`opam install x509.1.2.0`. Версии намеренно совпадают с официальными: overlay
должен иметь приоритет над обычным репозиторием. Обновить соответствующие
ограничения в корпоративных `.opam` и lock-файлах, если они фиксируют git URL.

Каталог `overlay/` также является самостоятельным opam-репозиторием:

```sh
opam repository add x509-overlay ./overlay
```

## Поведение и API

В 0.16.4 используется точный патч коммита `a307dd3`. При явном ID он
записывается в ключ и все переданные сертификаты. Без аргумента атрибут
`localKeyId` отсутствует — как в форке.

```ocaml
(* x509.0.16.4: fingerprint и local_key_id имеют тип Cstruct.t *)
let local_key_id = X509.Certificate.fingerprint `SHA1 cert in
let p12 = X509.PKCS12.create ~local_key_id password [cert] private_key
```

В 1.2.0 upstream уже вычисляет ID из публичного ключа. Патч добавляет
возможность переопределить его. Без аргумента upstream-поведение сохраняется.
В обоих случаях атрибут получает ключ и соответствующий ему сертификат;
остальные сертификаты цепочки остаются без этого атрибута.

```ocaml
(* x509.1.2.0: fingerprint и local_key_id имеют тип string *)
let local_key_id = X509.Certificate.fingerprint `SHA1 cert in
let p12 = X509.PKCS12.create ~local_key_id password [cert] private_key
```

Передаются исходные 20 байт SHA-1 fingerprint сертификата, без hex-кодирования.
Fingerprint сертификата отличается от fingerprint публичного ключа.
Если приложение само получает `Cstruct.t` из другого источника, на 1.2.0
потребуется `Cstruct.to_string` на границе API. Другие изменения API X509 1.x
этот патч не отменяет: сборку корпоративного приложения нужно проверить отдельно.

## Происхождение

- Официальные архивы: [0.16.4](https://github.com/mirleft/ocaml-x509/releases/tag/v0.16.4),
  [1.2.0](https://github.com/mirleft/ocaml-x509/releases/tag/v1.2.0).
- Metadata 0.16.4 взята из [opam-repository перед архивацией](https://github.com/ocaml/opam-repository/blob/08d8c16c16dc6b23a5278b06dff0ac6c7a217356/packages/x509/x509.0.16.4/opam).
  Автоматические ограничения, добавленные позже в архивном репозитории,
  не перенесены. Официальные ограничения Mirage Crypto `< 1.0.0` сохранены.
- Metadata 1.2.0 взята из официального opam-repository.
- Старый патч — [изменение NightBlues](https://github.com/NightBlues/ocaml-x509/commit/a307dd319b2896789926b3a85cbd544ca6ef81d0).
  Свежий патч переносит только управление ID, сохраняя выбор matching certificate.
- Старые пропатченные файлы совпадают с форком; в документационном заголовке
  `x509.mli` официальный архив уже подставил версию и homepage вместо шаблонов.

## Проверка

Python >= 3.12, opam, patch и OpenSSL должны быть доступны в PATH.
Проверка metadata и применения патчей без сборки:

```sh
python3 scripts/verify-overlay.py --check-only
```

Для полной проверки использовать switch с зависимостями нужной версии и её
`with-test` зависимостями. Скрипт ничего в switch не устанавливает.
Не передавайте каталог overlay-пакета в `opam install` как локальные исходники:
в нём находятся metadata и патчи, а исходники скачиваются из `url`.
Для установки используйте подключённый overlay и имя пакета с версией.

```sh
python3 scripts/verify-overlay.py --set legacy --switch=/path/to/legacy-switch
python3 scripts/verify-overlay.py --set latest --switch=/path/to/latest-switch
```

Проверены на OCaml 4.14.1 / Mirage Crypto 0.11.3 и OCaml 5.5.0 /
Mirage Crypto 2.4.1 соответственно. Оба пакета также установлены штатным opam
из локального overlay с `--with-test`.

Проверки включают lint, checksum архивов и патчей, применение без fuzz/offsets,
сборку, upstream-тесты, PKCS#12 round-trip и неверный пароль. OpenSSL отдельно
проверяет MAC и извлечение ключа/сертификатов, точные ID при явном значении
и без него, а также атрибуты дополнительного CA-сертификата. Все ключи и
сертификаты создаются во временном каталоге. Production-патч тестов не содержит.
