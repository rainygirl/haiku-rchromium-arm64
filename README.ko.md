# R Chromium -- arm64 (AArch64)

[English](README.md) | [日本語](README.ja.md) | **한국어**

Chromium의 `content_shell`을 Haiku/AArch64용으로 네이티브 빌드하고, 직접 작성한
BeAPI 툴바로 감싼 브라우저입니다. x86 에뮬레이션 없이 Apple Silicon(및 arm64
하드웨어)에서 네이티브 속도로 동작합니다. 이 문서는 최종 사용자용 설치 및 실행
안내입니다.

빌드, 아키텍처, 포팅 내부 사항은 [`AGENTS.md`](AGENTS.md)에 있습니다.

![Haiku arm64 데스크톱에서 news.naver.com을 렌더링하는 R Chromium](docs/images/screenshot-naver.png)

*RENKU(Haiku arm64) 데스크톱에서 네이티브 BeAPI 툴바와 함께 렌더링된
news.naver.com. Apple Silicon Mac의 QEMU/HVF VM에서 캡처.*

## 요구 사항

- **AArch64용 Haiku** -- 실제 renku-arm64 데스크톱(Apple Silicon에서 QEMU/HVF로
  부팅하거나 arm64 하드웨어).
- **이미지에 `A0001` runtime_loader TLSDESC 패치 적용.** clang이 생성하는
  `R_AARCH64_TLSDESC` 재배치를 기본 Haiku 로더는 처리하지 못하므로, 이 패치가
  없으면 바이너리가 로드되지 않습니다. 패치는
  `haiku_kernel_patches/A0001-arm64-runtime-loader-tlsdesc.patch`이며, 기존
  이미지의 `haiku.hpkg`에 적용하는 방법은 [`AGENTS.md`](AGENTS.md)에 있습니다.
- **Haiku 표준 폰트.** 텍스트는 시스템 폰트로 셰이핑/래스터화됩니다. 기본
  RENKU/Haiku 폰트 세트로 충분합니다(news.naver.com의 한글도 렌더링됨).

## 기기에 설치하고 실행하기

### 배포

바이너리, 리소스, BeAPI 심(`libchromium_haiku.so`)을 한곳에 둡니다. 예를 들어
쓰기 가능한 BFS 볼륨의 `cs/` 디렉터리:

```
cs/content_shell                 # 바이너리
cs/content_shell.pak             # 리소스 ...
cs/icudtl.dat
cs/snapshot_blob.bin
cs/v8_context_snapshot.bin
cs/locales/
cs/lib/libchromium_haiku.so      # 네이티브 BeAPI 툴바 심
```

### 실행

`content_shell`은 심이 필요하므로(`DT_NEEDED: libchromium_haiku`) 로더가
`cs/lib`을 찾도록 지정합니다. 실행 플래그는 필요 없습니다. Haiku에서는 빌드
자체가 소프트웨어 컴포지팅을 활성화합니다:

```sh
cd cs
LIBRARY_PATH=$(pwd)/lib:/boot/system/lib ./content_shell https://news.naver.com
```

툴바가 있는 네이티브 Haiku 창이 열리고 그 아래에 페이지가 렌더링됩니다.

### 브라우저 사용법

창 상단의 툴바는 BeAPI 컨트롤로 그려집니다:

- **뒤로 / 앞으로 / 새로고침** -- 왼쪽의 아이콘 버튼. 페이지 로딩 중에는
  새로고침이 중지 버튼으로 바뀝니다.
- **주소 입력란** -- URL을 입력하고 Enter를 누르면 이동합니다. `example.com`처럼
  스킴이 없으면 `https://example.com`으로 처리됩니다. 현재 페이지의 URL을
  따라갑니다.
- **북마크 추가(별)** -- 현재 페이지를 날짜 그룹("Today", ...) 아래 북마크
  저장소에 넣습니다.
- **북마크 보기** -- 검색 가능한 북마크 창을 엽니다. 항목을 더블클릭하면
  열립니다.

### 알려진 제한과 문제 해결

- **실행 시 `libchromium_haiku.so: Troubles handling dynamic section`** -- 심이
  4 KB 페이지로 링크되지 않았습니다. 올바른 빌드의 심을 사용하세요(재링크
  플래그와 이유는 [`AGENTS.md`](AGENTS.md) 참고).
- **`Bad data relocating` / 바이너리가 로드되지 않음** -- 이미지의 로더에
  `A0001` TLSDESC 패치가 없습니다(요구 사항 참고).
- news.naver.com 등 페이지가 네이티브 툴바, 주소창 탐색, 북마크와 함께 완전히
  렌더링됩니다. 전체 검증 이력과 알려진 미완성 부분은 [`AGENTS.md`](AGENTS.md)에
  있습니다.

## AI 활용 고지

이 프로그램은 Claude와 함께 작업해 만들었습니다.
