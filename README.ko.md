# R Chromium -- arm64 (AArch64)

[English](README.md) | [日本語](README.ja.md) | **한국어**

Haiku/AArch64(Apple Silicon 및 기타 arm64 기기)에서 네이티브로 동작하는
Chromium입니다. 뒤로/앞으로/새로고침, 주소 입력란, 북마크로 이루어진 BeAPI
툴바가 붙어 있습니다. RENKU arm64 이미지(TLSDESC 로더 패치가 적용된 Haiku
arm64)에서 동작하며, 순정 Haiku arm64 이미지에서는 로드되지 않습니다.

![Haiku arm64 데스크톱에서 news.naver.com을 렌더링하는 R Chromium](docs/images/screenshot-naver.png)

## 설치

기기에서 Terminal을 열고 아래 한 줄을 붙여 넣습니다:

```sh
python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/rainygirl/haiku-rchromium-arm64/main/install.py').read())"
```

최신 릴리스(약 110 MB)를 내려받아 `~/config/non-packaged/apps/RChromium/`에
설치하고, **Deskbar -> Applications**와 데스크톱에 **R Chromium**을 추가하며,
`rchromium` 명령을 만듭니다. `/boot`에 약 350 MB의 여유 공간이 필요합니다.

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
