# 여주예총 홈페이지 (리뉴얼 시안)

사단법인 한국예총 경기도연합회 여주지회 홈페이지(yeojuart.co.kr, 그누보드4)를 서버 프로그램 없이 동작하는 정적 사이트로 다시 만든 것입니다.
글은 `content/` 폴더의 파일로, 사진과 첨부파일은 `uploads/` 폴더에 저장됩니다.

## 글 쓰는 방법 (담당자용)

1. https://app.pagescms.org 에 접속해 로그인합니다.
   - GitHub 계정이 없는 담당자는 저장소 관리자가 **이메일로 초대**(Pages CMS의 Collaborators)하면 그 이메일로 로그인할 수 있습니다.
2. `art_yj` 저장소를 엽니다. 왼쪽에 **공지사항 · 행사·축제 · 포토갤러리 · 회원단체 소개**가 나옵니다.
3. **Add an entry**(새 글)를 누르고 제목, 작성일, 본문을 입력한 뒤 **Save**를 누릅니다.
   - 본문에 사진을 넣거나 첨부파일(한글·PDF 등)을 올릴 수 있습니다.
   - 사진은 휴대폰 원본 그대로 올려도 됩니다. 저장 후 **긴 변 1600px 이하로 자동으로 줄여** 다시 저장합니다.
   - 각 협회는 **회원단체 소개**에서 인사말, 대표자, 한 줄 소개, 사진을 고칠 수 있습니다.
4. 저장하고 1~3분 뒤 홈페이지에 반영됩니다. (진행 상황: 저장소의 **Actions** 탭)

## 구조

| 경로 | 내용 |
|---|---|
| `site.yml` | 단체 정보, 메뉴, 게시판, 임원 명단, 관련 사이트 |
| `content/notice`, `events`, `gallery` | 게시글 (위쪽 `---` 사이에 제목·날짜·첨부, 그 아래 본문) |
| `content/associations/*.md` | 6개 회원단체 소개 |
| `uploads/` | 사진·첨부파일 (`migrated/` 는 기존 사이트에서 옮겨 온 파일) |
| `templates/`, `css/` | 페이지 디자인 |
| `scripts/build.py` | 글 파일로 사이트를 만드는 프로그램 |
| `scripts/migrate_old_site.py` | 기존 사이트 게시글을 한 번 옮겨 오기 (끝나면 `data/migrated.txt` 생성) |
| `scripts/resize_images.py` | 큰 사진 자동 축소 |
| `.pages.yml` | 글쓰기 화면(Pages CMS) 설정 |
| `.github/workflows/deploy.yml` | 저장할 때마다 글 옮기기·사진 축소 → 사이트 생성 → 배포 |

## 처음 설정 (한 번만)

- 저장소 **Settings → Pages → Build and deployment → Source** 를 **GitHub Actions** 로 바꿉니다.
- 자체 도메인으로 옮길 때는 `site.yml` 의 `baseurl` 을 `""` 로, `draft` 를 `false` 로 바꿉니다.
