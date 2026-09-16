# R Chromium -- arm64 (AArch64)

[English](README.md) | [日本語](README.ja.md) | **한국어**

Haiku/AArch64(Apple Silicon 및 기타 arm64 기기)에서 네이티브로 동작하는
Chromium입니다. 뒤로/앞으로/새로고침, 주소 입력란, 북마크로 이루어진 BeAPI
툴바가 붙어 있습니다. Noto Sans CJK를 내장해 한국어, 일본어, 중국어 페이지가
추가 폰트 없이 표시됩니다. RENKU arm64 이미지(TLSDESC 로더 패치가 적용된 Haiku
arm64)에서 동작하며, 순정 Haiku arm64 이미지에서는 로드되지 않습니다.

![Haiku arm64 데스크톱에서 news.naver.com을 렌더링하는 R Chromium](docs/images/screenshot-naver.png)

## pkgman으로 설치

R Chromium은 `pkgman.rainygirl.com` 패키지 저장소에 올라가 있습니다. 기기에서
Terminal을 열고 입력합니다:

```sh
pkgman add-repo https://pkgman.rainygirl.com/arm64
pkgman add-repo https://pkgman.rainygirl.com/arm64-system
pkgman install rchromium
```

그다음 **재부팅**합니다. R Chromium은 RenkuOS nightly arm64 이미지에 아직 없는
커널·런타임 로더 수정 두 가지(TLSDESC 로더 패치, `query-valid-pte` 커널 패치)가
필요합니다. `arm64-system` 저장소가 두 수정을 넣은 `haiku` 시스템 패키지를
제공하며, `pkgman install rchromium`이 의존성으로 함께 설치합니다. 다음 부팅부터
적용되고, 그전에는 R Chromium이 `Troubles relocating: Bad data`로 종료되거나
커널이 패닉합니다.

패키지는 약 150 MB이니 `/boot`에 그만큼 여유 공간이 있어야 합니다.
`/boot/system/apps/RChromium/`에 설치되고, **Deskbar -> Applications**에
**R Chromium**이 추가되며 `rchromium` 명령이 생깁니다. 제거는
`pkgman uninstall rchromium`입니다.

`pkgman add-repo`가 `Operation not supported`로 실패하면, 그 이미지는 네트워크
킷에 TLS 지원 없이 빌드된 것입니다(RenkuOS nightly minimum 이미지가 그렇습니다).
이 이미지는 1970-01-01로 부팅하므로 먼저 시계를 맞추고 HTTP 주소를 사용합니다:

```sh
date -u 091612002026        # MMDDhhmmYYYY, 현재 UTC 시각
yes | pkgman add-repo http://pkgman.rainygirl.com/arm64
yes | pkgman add-repo http://pkgman.rainygirl.com/arm64-system
pkgman install rchromium
```

설치 후 재부팅합니다. 이 이미지는 부팅할 때마다 시계가 다시 1970으로 돌아가므로,
R Chromium을 실행하기 전에 시계를 맞추세요. 안 맞추면 모든 HTTPS 사이트가
`ERR_CERT_DATE_INVALID`로 실패합니다.

`yes |`는 HTTPS 시도가 실패하며 남긴 저장소 설정 때문에 pkgman이 묻는
"overwrite?"에 답하기 위한 것입니다.

## 설치 스크립트로 설치

기기에서 Terminal을 열고 아래 한 줄을 붙여 넣습니다:

```sh
python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/rainygirl/haiku-rchromium-arm64/main/install.py').read())"
```

최신 릴리스(약 140 MB)를 내려받아 `~/config/non-packaged/apps/RChromium/`에
설치하고, **Deskbar -> Applications**와 데스크톱에 **R Chromium**을 추가하며,
`rchromium` 명령을 만듭니다. `/boot`에 약 400 MB의 여유 공간이 필요합니다.

이 저장소를 체크아웃했다면 `./install.sh`도 같은 일을 합니다.

## 실행

데스크톱의 **R Chromium**을 더블클릭하거나 **Deskbar -> Applications**에서
고릅니다. Terminal에서는:

```sh
rchromium https://news.naver.com
```

- **뒤로 / 앞으로 / 새로고침** -- 왼쪽의 아이콘 버튼. 페이지 로딩 중에는
  새로고침이 중지 버튼으로 바뀝니다.
- **주소 입력란** -- URL을 입력하고 Enter. `example.com`처럼 입력하면
  `https://example.com`을 엽니다.
- **별** -- 현재 페이지를 날짜 그룹("Today", ...) 아래에 북마크합니다.
- **메뉴** -- 검색 가능한 북마크 창을 엽니다. 항목을 더블클릭하면 열립니다.

## 제거

```sh
python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/rainygirl/haiku-rchromium-arm64/main/install.py').read())" --uninstall
```

체크아웃에서는 `./install.sh --uninstall`.

## AI 활용 고지

이 프로그램은 Claude와 함께 작업해 만들었습니다.
