// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Built with the same gcc that built libbe, not with Chromium's clang. See
// haiku_shim.h for why the BeAPI subclasses cannot live inside Chromium.
//
// The native toolbar is drawn with BControlLook (the same primitives the rest
// of Haiku draws its arrows and button frames with) rather than with BButtons
// carrying bitmaps, so it follows the user's colour scheme and decorator and
// needs no icon artwork. This matches the x86 port (rchromium-native-x86,
// chromium87_overlay/ozone/haiku_beapi_views.cc); the two were converged on
// this style by user decision on 2026-09-13.

#include "haiku_shim.h"

#include <Application.h>
#include <Autolock.h>
#include <Bitmap.h>
#include <ControlLook.h>
#include <Directory.h>
#include <File.h>
#include <FindDirectory.h>
#include <InterfaceDefs.h>
#include <ListItem.h>
#include <Locker.h>
#include <Message.h>
#include <OS.h>
#include <OutlineListView.h>
#include <Path.h>
#include <Rect.h>
#include <Screen.h>
#include <ScrollView.h>
#include <StringItem.h>
#include <TextControl.h>
#include <TextView.h>
#include <View.h>
#include <Window.h>

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include <algorithm>
#include <string>
#include <vector>

namespace haiku_shim {

namespace {

// The signature app_server files this team under. It has to be a valid MIME
// type or BApplication refuses to construct.
const char kAppSignature[] = "application/x-vnd.Chromium-Ozone";

sem_id g_app_ready = -1;
bool g_app_started = false;

int32 AppThreadEntry(void*) {
  // Stack-allocated and never destroyed: Run() only returns when the
  // application quits, which for this process means the whole team is going
  // away anyway.
  BApplication app(kAppSignature);
  // The constructor above sets be_app, so windows can be built from this
  // point on; callers do not have to wait for Run() to reach its loop.
  release_sem(g_app_ready);
  app.Run();
  return 0;
}

class ShimView : public BView {
 public:
  ShimView(BRect frame, Delegate* delegate)
      : BView(frame,
              "ChromiumView",
              B_FOLLOW_ALL_SIDES,
              B_WILL_DRAW | B_FRAME_EVENTS | B_NAVIGABLE),
        delegate_(delegate),
        bitmap_(NULL) {
    SetViewColor(B_TRANSPARENT_COLOR);
  }

  ~ShimView() { delete bitmap_; }

  // Takes ownership of a copy of the pixels so Draw() can repaint without
  // asking the compositor for another frame.
  void SetFrontBuffer(BBitmap* bitmap) {
    delete bitmap_;
    bitmap_ = bitmap;
  }

  void Draw(BRect update) {
    if (bitmap_ != NULL) {
      DrawBitmap(bitmap_, update, update);
    }
  }

  void MouseDown(BPoint where) {
    int32 buttons = 0;
    int32 clicks = 1;
    BMessage* msg = BView::Window()->CurrentMessage();
    if (msg != NULL) {
      msg->FindInt32("buttons", &buttons);
      msg->FindInt32("clicks", &clicks);
    }
    delegate_->OnMouseDown(where.x, where.y, modifiers(), buttons, clicks);
  }

  void MouseUp(BPoint where) {
    int32 buttons = 0;
    BMessage* msg = BView::Window()->CurrentMessage();
    if (msg != NULL) {
      msg->FindInt32("buttons", &buttons);
    }
    delegate_->OnMouseUp(where.x, where.y, modifiers(), buttons);
  }

  void MouseMoved(BPoint where, uint32 transit, const BMessage*) {
    int32 buttons = 0;
    BMessage* msg = BView::Window()->CurrentMessage();
    if (msg != NULL) {
      msg->FindInt32("buttons", &buttons);
    }
    delegate_->OnMouseMoved(where.x, where.y, modifiers(), buttons, transit);
  }

  void KeyDown(const char* bytes, int32 numBytes) {
    delegate_->OnKey(true, bytes, numBytes, modifiers());
  }

  void KeyUp(const char* bytes, int32 numBytes) {
    delegate_->OnKey(false, bytes, numBytes, modifiers());
  }

  void FrameResized(float width, float height) {
    delegate_->OnViewResized(width, height);
  }

 private:
  Delegate* delegate_;
  BBitmap* bitmap_;
};

// ------------------------------------------------------------- native toolbar

const uint32 kMsgBack = 'rchB';
const uint32 kMsgForward = 'rchF';
const uint32 kMsgReloadStop = 'rchR';
const uint32 kMsgGo = 'rchG';
const uint32 kMsgAddBookmark = 'rchA';
const uint32 kMsgOpenBookmarks = 'rchL';

const float kChromeHeight = 30.0f;
const float kButtonSize = 24.0f;
const float kPadding = 3.0f;

const char kChromeViewName[] = "rchromium chrome";

class ChromeButton : public BView {
 public:
  enum class Glyph { kBack, kForward, kReload, kStop, kStar, kList };

  ChromeButton(BRect frame, const char* name, Glyph glyph, uint32 what)
      : BView(frame, name, B_FOLLOW_LEFT | B_FOLLOW_TOP, B_WILL_DRAW),
        glyph_(glyph),
        what_(what) {
    SetViewUIColor(B_PANEL_BACKGROUND_COLOR);
  }

  void SetGlyph(Glyph glyph) {
    if (glyph_ == glyph)
      return;
    glyph_ = glyph;
    Invalidate();
  }

  void SetEnabled(bool enabled) {
    if (enabled_ == enabled)
      return;
    enabled_ = enabled;
    Invalidate();
  }

  void Draw(BRect update_rect) override {
    const rgb_color base = ui_color(B_PANEL_BACKGROUND_COLOR);
    BRect rect = Bounds();
    uint32 flags = 0;
    if (!enabled_)
      flags |= BControlLook::B_DISABLED;
    if (pressed_)
      flags |= BControlLook::B_ACTIVATED;

    be_control_look->DrawButtonFrame(this, rect, update_rect, base, base,
                                     flags);
    be_control_look->DrawButtonBackground(this, rect, update_rect, base,
                                          flags);

    // rect has been inset by the frame and background passes; centre the
    // glyph in what is left.
    switch (glyph_) {
      case Glyph::kBack:
        be_control_look->DrawArrowShape(this, rect, update_rect, base,
                                        BControlLook::B_LEFT_ARROW, flags);
        break;
      case Glyph::kForward:
        be_control_look->DrawArrowShape(this, rect, update_rect, base,
                                        BControlLook::B_RIGHT_ARROW, flags);
        break;
      case Glyph::kReload:
        DrawReload(rect, base, flags);
        break;
      case Glyph::kStop:
        DrawStop(rect, base, flags);
        break;
      case Glyph::kStar:
        DrawStar(rect, base, flags);
        break;
      case Glyph::kList:
        DrawList(rect, base, flags);
        break;
    }
  }

  void MouseDown(BPoint where) override {
    if (!enabled_)
      return;
    pressed_ = true;
    SetMouseEventMask(B_POINTER_EVENTS, B_LOCK_WINDOW_FOCUS);
    Invalidate();
  }

  void MouseUp(BPoint where) override {
    if (!pressed_)
      return;
    pressed_ = false;
    Invalidate();
    if (enabled_ && Bounds().Contains(where) && Window() != NULL)
      Window()->PostMessage(what_, Parent());
  }

 private:
  // A three-quarter circle with an arrow head, the usual reload shape. There
  // is no BControlLook primitive for it, so stroke it directly.
  void DrawReload(BRect rect, const rgb_color& base, uint32 flags) {
    PushState();
    SetHighColor(Ink(base, flags));
    SetPenSize(2.0f);
    SetFlags(Flags() | B_SUBPIXEL_PRECISE);

    const BPoint center(rect.left + rect.Width() / 2.0f,
                        rect.top + rect.Height() / 2.0f);
    const float radius = std::min(rect.Width(), rect.Height()) / 2.0f - 2.0f;
    StrokeArc(center, radius, radius, 300.0f, 300.0f);

    // Arrow head at the open end of the arc, pointing clockwise.
    const float head = radius * 0.55f;
    const BPoint tip(center.x + radius, center.y);
    BPoint points[3] = {
        BPoint(tip.x, tip.y - head),
        BPoint(tip.x - head * 0.8f, tip.y + head * 0.2f),
        BPoint(tip.x + head * 0.8f, tip.y + head * 0.2f),
    };
    FillPolygon(points, 3);
    PopState();
  }

  // Add-bookmark. A five-pointed star, computed rather than drawn from a
  // table so it scales with the button.
  void DrawStar(BRect rect, const rgb_color& base, uint32 flags) {
    PushState();
    SetHighColor(Ink(base, flags));
    const BPoint center(rect.left + rect.Width() / 2.0f,
                        rect.top + rect.Height() / 2.0f);
    const float outer = std::min(rect.Width(), rect.Height()) / 2.0f - 1.0f;
    const float inner = outer * 0.42f;
    BPoint points[10];
    for (int i = 0; i < 10; ++i) {
      // Start at -90 degrees so a point is at the top.
      const double angle = (-90.0 + i * 36.0) * 3.14159265358979 / 180.0;
      const float radius = (i % 2 == 0) ? outer : inner;
      points[i] = BPoint(center.x + radius * static_cast<float>(cos(angle)),
                         center.y + radius * static_cast<float>(sin(angle)));
    }
    FillPolygon(points, 10);
    PopState();
  }

  // Open the bookmark list. Three stacked rules, the usual list glyph.
  void DrawList(BRect rect, const rgb_color& base, uint32 flags) {
    PushState();
    SetHighColor(Ink(base, flags));
    SetPenSize(2.0f);
    BRect inner = rect;
    inner.InsetBy(rect.Width() * 0.22f, rect.Height() * 0.26f);
    const float step = inner.Height() / 2.0f;
    for (int i = 0; i < 3; ++i) {
      const float y = inner.top + i * step;
      StrokeLine(BPoint(inner.left, y), BPoint(inner.right, y));
    }
    PopState();
  }

  void DrawStop(BRect rect, const rgb_color& base, uint32 flags) {
    PushState();
    SetHighColor(Ink(base, flags));
    SetPenSize(2.0f);
    BRect x = rect;
    x.InsetBy(rect.Width() * 0.28f, rect.Height() * 0.28f);
    StrokeLine(BPoint(x.left, x.top), BPoint(x.right, x.bottom));
    StrokeLine(BPoint(x.left, x.bottom), BPoint(x.right, x.top));
    PopState();
  }

  static rgb_color Ink(const rgb_color& base, uint32 flags) {
    return (flags & BControlLook::B_DISABLED) != 0
               ? tint_color(base, B_DARKEN_2_TINT)
               : tint_color(base, B_DARKEN_MAX_TINT);
  }

  Glyph glyph_;
  uint32 what_;
  bool enabled_ = false;
  bool pressed_ = false;
};

// ------------------------------------------------------------------ bookmarks

struct Bookmark {
  time_t when = 0;
  std::string url;
  std::string title;
};

// Bookmarks on disk, one per line, as "<unix seconds>\t<url>\t<title>". A
// settings file rather than a BFS attribute directory, so it survives being
// copied off a BFS volume. Tabs and newlines in a title become spaces. The
// format matches the x86 port so a profile is portable between the two.
class BookmarkStore {
 public:
  static BookmarkStore& Get() {
    static BookmarkStore* instance = new BookmarkStore();
    return *instance;
  }

  void Add(const std::string& url, const std::string& title) {
    if (url.empty())
      return;
    Bookmark entry;
    entry.when = time(NULL);
    entry.url = Sanitise(url);
    entry.title = Sanitise(title.empty() ? url : title);

    BAutolock guard(lock_);
    EnsureLoaded();
    // Re-bookmarking a page moves it to today rather than duplicating.
    for (size_t i = 0; i < items_.size(); ++i) {
      if (items_[i].url == entry.url) {
        items_.erase(items_.begin() + i);
        break;
      }
    }
    items_.push_back(entry);
    Save();
  }

  std::vector<Bookmark> All() {
    BAutolock guard(lock_);
    EnsureLoaded();
    return items_;
  }

 private:
  BookmarkStore() : lock_("rchromium bookmarks") {}

  static std::string Sanitise(const std::string& text) {
    std::string out = text;
    for (size_t i = 0; i < out.size(); ++i) {
      if (out[i] == '\t' || out[i] == '\n' || out[i] == '\r')
        out[i] = ' ';
    }
    return out;
  }

  static bool SettingsPath(BPath* path) {
    if (find_directory(B_USER_SETTINGS_DIRECTORY, path) != B_OK)
      return false;
    if (path->Append("RChromium") != B_OK)
      return false;
    create_directory(path->Path(), 0755);
    return path->Append("bookmarks") == B_OK;
  }

  void EnsureLoaded() {
    if (loaded_)
      return;
    loaded_ = true;

    BPath path;
    if (!SettingsPath(&path))
      return;
    BFile file(path.Path(), B_READ_ONLY);
    if (file.InitCheck() != B_OK)
      return;
    off_t size = 0;
    if (file.GetSize(&size) != B_OK || size <= 0)
      return;
    std::string text(static_cast<size_t>(size), '\0');
    if (file.Read(&text[0], text.size()) != static_cast<ssize_t>(text.size()))
      return;

    size_t start = 0;
    while (start < text.size()) {
      size_t end = text.find('\n', start);
      if (end == std::string::npos)
        end = text.size();
      ParseLine(text.substr(start, end - start));
      start = end + 1;
    }
  }

  void ParseLine(const std::string& line) {
    const size_t first = line.find('\t');
    if (first == std::string::npos)
      return;
    const size_t second = line.find('\t', first + 1);
    if (second == std::string::npos)
      return;
    Bookmark entry;
    entry.when = static_cast<time_t>(atoll(line.substr(0, first).c_str()));
    entry.url = line.substr(first + 1, second - first - 1);
    entry.title = line.substr(second + 1);
    if (!entry.url.empty())
      items_.push_back(entry);
  }

  void Save() {
    BPath path;
    if (!SettingsPath(&path))
      return;
    BFile file(path.Path(), B_WRITE_ONLY | B_CREATE_FILE | B_ERASE_FILE);
    if (file.InitCheck() != B_OK)
      return;
    for (size_t i = 0; i < items_.size(); ++i) {
      char header[32];
      snprintf(header, sizeof(header), "%lld\t",
               static_cast<long long>(items_[i].when));
      std::string line = header + items_[i].url + "\t" + items_[i].title + "\n";
      file.Write(line.data(), line.size());
    }
  }

  BLocker lock_;
  std::vector<Bookmark> items_;
  bool loaded_ = false;
};

// "Today", "Yesterday", or the date, by local calendar day.
std::string DateGroupLabel(time_t when) {
  const time_t now = time(NULL);
  struct tm entry;
  struct tm today;
  struct tm yesterday;
  const time_t a_day_ago = now - 24 * 60 * 60;
  if (localtime_r(&when, &entry) == NULL ||
      localtime_r(&now, &today) == NULL ||
      localtime_r(&a_day_ago, &yesterday) == NULL) {
    return "Bookmarks";
  }
  if (entry.tm_year == today.tm_year && entry.tm_yday == today.tm_yday)
    return "Today";
  if (entry.tm_year == yesterday.tm_year && entry.tm_yday == yesterday.tm_yday)
    return "Yesterday";
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%d", &entry);
  return buf;
}

bool ContainsNoCase(const std::string& haystack, const std::string& needle) {
  if (needle.empty())
    return true;
  if (needle.size() > haystack.size())
    return false;
  for (size_t i = 0; i + needle.size() <= haystack.size(); ++i) {
    size_t j = 0;
    while (j < needle.size() &&
           tolower(static_cast<unsigned char>(haystack[i + j])) ==
               tolower(static_cast<unsigned char>(needle[j]))) {
      ++j;
    }
    if (j == needle.size())
      return true;
  }
  return false;
}

class BookmarkItem : public BStringItem {
 public:
  BookmarkItem(const std::string& label, const std::string& url)
      : BStringItem(label.c_str(), 1, true), url_(url) {}

  const std::string& url() const { return url_; }

 private:
  std::string url_;
};

const uint32 kMsgBookmarkSearch = 'rchS';
const uint32 kMsgBookmarkOpen = 'rchO';

// Opening a bookmark calls this back on the bookmarks-window looper thread; the
// shim Delegate hops to Chromium's UI thread itself.
class BookmarkOpener {
 public:
  virtual void OpenURL(const std::string& url) = 0;

 protected:
  ~BookmarkOpener() {}
};

class BookmarksWindow : public BWindow {
 public:
  explicit BookmarksWindow(BookmarkOpener* opener)
      : BWindow(BRect(120, 120, 620, 520), "Bookmarks", B_TITLED_WINDOW,
                B_ASYNCHRONOUS_CONTROLS),
        opener_(opener) {
    BRect bounds = Bounds();

    BRect search_frame(kPadding, kPadding, bounds.right - kPadding,
                       kPadding + 22);
    search_ = new BTextControl(search_frame, "search", NULL, "",
                               new BMessage(kMsgBookmarkSearch),
                               B_FOLLOW_LEFT_RIGHT | B_FOLLOW_TOP);
    search_->SetDivider(0.0f);
    search_->SetModificationMessage(new BMessage(kMsgBookmarkSearch));
    AddChild(search_);

    BRect list_frame(kPadding, search_frame.bottom + kPadding,
                     bounds.right - kPadding - B_V_SCROLL_BAR_WIDTH,
                     bounds.bottom - kPadding);
    list_ = new BOutlineListView(list_frame, "bookmarks",
                                 B_SINGLE_SELECTION_LIST, B_FOLLOW_ALL_SIDES);
    list_->SetInvocationMessage(new BMessage(kMsgBookmarkOpen));
    AddChild(new BScrollView("scroller", list_, B_FOLLOW_ALL_SIDES, 0, false,
                             true));

    Rebuild();
  }

  bool QuitRequested() override {
    Hide();
    return false;
  }

  void MessageReceived(BMessage* message) override {
    switch (message->what) {
      case kMsgBookmarkSearch:
        Rebuild();
        return;
      case kMsgBookmarkOpen:
        OpenSelection();
        return;
      default:
        BWindow::MessageReceived(message);
    }
  }

  void Refresh() {
    if (!Lock())
      return;
    Rebuild();
    Unlock();
  }

 private:
  void OpenSelection() {
    const int32 index = list_->CurrentSelection();
    if (index < 0)
      return;
    BookmarkItem* item = dynamic_cast<BookmarkItem*>(list_->ItemAt(index));
    if (item != NULL)
      opener_->OpenURL(item->url());
  }

  static bool Newer(const Bookmark& a, const Bookmark& b) {
    return a.when > b.when;
  }

  void Rebuild() {
    search_->SetTarget(this);
    list_->SetTarget(this);

    while (BListItem* item = list_->RemoveItem(int32(0)))
      delete item;

    std::vector<Bookmark> entries = BookmarkStore::Get().All();
    std::sort(entries.begin(), entries.end(), Newer);

    const std::string query =
        search_->Text() != NULL ? std::string(search_->Text()) : "";

    std::string open_group;
    for (size_t i = 0; i < entries.size(); ++i) {
      const Bookmark& entry = entries[i];
      if (!ContainsNoCase(entry.title, query) &&
          !ContainsNoCase(entry.url, query)) {
        continue;
      }
      const std::string group = DateGroupLabel(entry.when);
      if (group != open_group) {
        list_->AddItem(new BStringItem(group.c_str(), 0, false));
        open_group = group;
      }
      const std::string label =
          entry.title.empty() ? entry.url : entry.title + "  -  " + entry.url;
      list_->AddItem(new BookmarkItem(label, entry.url));
    }
  }

  BookmarkOpener* opener_;
  BTextControl* search_ = NULL;
  BOutlineListView* list_ = NULL;
};

// The toolbar view: icon-only Back/Forward/Reload, the address field, then the
// add-bookmark and open-bookmarks buttons at the right edge.
class BrowserChromeView : public BView, public BookmarkOpener {
 public:
  BrowserChromeView(BRect frame, Delegate* delegate)
      : BView(frame, kChromeViewName, B_FOLLOW_LEFT_RIGHT | B_FOLLOW_TOP,
              B_WILL_DRAW | B_FRAME_EVENTS),
        delegate_(delegate) {
    SetViewUIColor(B_PANEL_BACKGROUND_COLOR);

    float x = kPadding;
    back_ = AddButton(&x, "back", ChromeButton::Glyph::kBack, kMsgBack);
    forward_ =
        AddButton(&x, "forward", ChromeButton::Glyph::kForward, kMsgForward);
    reload_ =
        AddButton(&x, "reload", ChromeButton::Glyph::kReload, kMsgReloadStop);
    reload_->SetEnabled(true);

    star_ = new ChromeButton(BRect(0, 0, kButtonSize - 1, kButtonSize - 1),
                             "add bookmark", ChromeButton::Glyph::kStar,
                             kMsgAddBookmark);
    star_->SetEnabled(true);
    AddChild(star_);
    bookmarks_ = new ChromeButton(BRect(0, 0, kButtonSize - 1, kButtonSize - 1),
                                  "bookmarks", ChromeButton::Glyph::kList,
                                  kMsgOpenBookmarks);
    bookmarks_->SetEnabled(true);
    AddChild(bookmarks_);

    address_ = new BTextControl(AddressFrame(x), "address", NULL, "",
                                new BMessage(kMsgGo),
                                B_FOLLOW_LEFT_RIGHT | B_FOLLOW_TOP);
    address_->SetDivider(0.0f);
    AddChild(address_);
    address_left_ = x;
    Layout(Bounds().Width());
  }

  ~BrowserChromeView() override {
    if (bookmarks_window_ != NULL)
      bookmarks_window_->PostMessage(B_QUIT_REQUESTED);
  }

  void AttachedToWindow() override {
    BView::AttachedToWindow();
    address_->SetTarget(this);
  }

  void FrameResized(float width, float height) override {
    BView::FrameResized(width, height);
    Layout(width);
  }

  void MessageReceived(BMessage* message) override {
    switch (message->what) {
      case kMsgBack:
        delegate_->OnNavigateBack();
        return;
      case kMsgForward:
        delegate_->OnNavigateForward();
        return;
      case kMsgReloadStop:
        delegate_->OnReloadOrStop();
        return;
      case kMsgGo:
        delegate_->OnNavigateToURL(
            address_->Text() != NULL ? address_->Text() : "");
        return;
      case kMsgAddBookmark:
        BookmarkStore::Get().Add(current_url_, current_title_);
        if (bookmarks_window_ != NULL)
          bookmarks_window_->Refresh();
        return;
      case kMsgOpenBookmarks:
        ShowBookmarks();
        return;
      default:
        BView::MessageReceived(message);
    }
  }

  void SetAddress(const char* url) {
    current_url_ = url != NULL ? url : "";
    // Do not fight the user: a load finishing while they type must not replace
    // what is in the field.
    if (address_->TextView() != NULL && address_->TextView()->IsFocus())
      return;
    address_->SetText(url);
  }

  void SetPageTitle(const char* title) {
    current_title_ = title != NULL ? title : "";
  }

  void SetLoading(bool is_loading) {
    reload_->SetGlyph(is_loading ? ChromeButton::Glyph::kStop
                                 : ChromeButton::Glyph::kReload);
  }

  void SetNav(bool can_go_back, bool can_go_forward) {
    back_->SetEnabled(can_go_back);
    forward_->SetEnabled(can_go_forward);
  }

  // BookmarkOpener: on the bookmarks-window looper thread.
  void OpenURL(const std::string& url) override {
    delegate_->OnNavigateToURL(url.c_str());
  }

 private:
  void ShowBookmarks() {
    if (bookmarks_window_ == NULL)
      bookmarks_window_ = new BookmarksWindow(this);
    else
      bookmarks_window_->Refresh();
    if (bookmarks_window_->Lock()) {
      if (bookmarks_window_->IsHidden())
        bookmarks_window_->Show();
      bookmarks_window_->Activate(true);
      bookmarks_window_->Unlock();
    }
  }

  void Layout(float width) {
    const float top = (kChromeHeight - kButtonSize) / 2.0f;
    const float right_block = 2 * (kButtonSize + kPadding);
    bookmarks_->MoveTo(width - kButtonSize - kPadding, top);
    star_->MoveTo(width - 2 * kButtonSize - 2 * kPadding, top);
    const float address_width = width - address_left_ - kPadding - right_block;
    address_->ResizeTo(address_width > 40.0f ? address_width : 40.0f,
                       address_->Bounds().Height());
  }

  ChromeButton* AddButton(float* x,
                          const char* name,
                          ChromeButton::Glyph glyph,
                          uint32 what) {
    const float top = (kChromeHeight - kButtonSize) / 2.0f;
    BRect frame(*x, top, *x + kButtonSize - 1, top + kButtonSize - 1);
    ChromeButton* button = new ChromeButton(frame, name, glyph, what);
    AddChild(button);
    *x += kButtonSize + kPadding;
    return button;
  }

  BRect AddressFrame(float left) const {
    return BRect(left, kPadding, Bounds().right - kPadding,
                 kChromeHeight - kPadding - 1);
  }

  Delegate* delegate_;
  ChromeButton* back_ = NULL;
  ChromeButton* forward_ = NULL;
  ChromeButton* reload_ = NULL;
  ChromeButton* star_ = NULL;
  ChromeButton* bookmarks_ = NULL;
  BTextControl* address_ = NULL;
  float address_left_ = 0.0f;
  std::string current_url_;
  std::string current_title_;
  BookmarksWindow* bookmarks_window_ = NULL;
};

class ShimWindow : public BWindow, public NativeWindow {
 public:
  ShimWindow(BRect frame, bool has_frame, bool with_toolbar, Delegate* delegate)
      // Borderless is a window_look, not a window_type: the window_type enum
      // has no undecorated member, so this takes the look/feel constructor
      // and names the decoration directly.
      // `frame` is the CONTENT rect Chromium asked for. With a toolbar the
      // window is taller by kChromeHeight so the content view gets exactly
      // that size, and every frame reported back (FrameMoved, GetWindowFrame)
      // is the content rect again -- Chromium never sees the toolbar strip.
      : BWindow(WindowFrameForContent(frame, with_toolbar),
                "Chromium",
                has_frame ? B_TITLED_WINDOW_LOOK : B_NO_BORDER_WINDOW_LOOK,
                B_NORMAL_WINDOW_FEEL,
                B_ASYNCHRONOUS_CONTROLS),
        delegate_(delegate),
        has_frame_(has_frame),
        with_toolbar_(with_toolbar) {
    // The content view is built already inset below the toolbar, so it reports
    // one correct size to Chromium instead of a mid-resize sequence. (The x86
    // port instead insets an already-shown view and had to pin it
    // B_FOLLOW_NONE during the resize to stop aura seeing intermediate bounds
    // and stalling the renderer; building inset up front avoids that.)
    BRect content = Bounds();
    if (with_toolbar) {
      BRect chrome_frame = Bounds();
      chrome_frame.bottom = chrome_frame.top + kChromeHeight - 1;
      chrome_ = new BrowserChromeView(chrome_frame, delegate);
      AddChild(chrome_);
      content.top = kChromeHeight;
    }
    view_ = new ShimView(content, delegate);
    AddChild(view_);
    // Chromium places its first window at (0,0), which puts a titled
    // window's tab above the screen edge where nobody can see or grab it.
    KeepDecorOnScreen();
    // BWindow's constructor leaves the looper locked and does not start its
    // thread; Run() spawns it and drops the lock. Show() asserts the looper is
    // locked, so running here is what makes a later Show() safe.
    Run();
  }

  bool QuitRequested() {
    delegate_->OnQuitRequested();
    return false;
  }

  void WindowActivated(bool active) { delegate_->OnActivated(active); }

  void FrameMoved(BPoint origin) {
    BRect c = ContentFrame();
    delegate_->OnFrameMoved(c.left, c.top, c.Width() + 1, c.Height() + 1);
  }

  // NativeWindow:
  void ShowWindow(bool inactive) {
    if (!LockLooper()) {
      return;
    }
    BWindow::Show();
    if (inactive) {
      BWindow::Activate(false);
    }
    UnlockLooper();
  }

  void HideWindow() {
    if (!LockLooper()) {
      return;
    }
    BWindow::Hide();
    UnlockLooper();
  }

  void SetWindowBounds(float x, float y, float width, float height) {
    if (!LockLooper()) {
      return;
    }
    BRect f = WindowFrameForContent(BRect(x, y, x + width - 1, y + height - 1),
                                    with_toolbar_);
    MoveTo(f.left, f.top);
    ResizeTo(f.Width(), f.Height());
    KeepDecorOnScreen();
    UnlockLooper();
  }

  void GetWindowFrame(float out_xywh[4]) {
    out_xywh[0] = out_xywh[1] = out_xywh[2] = out_xywh[3] = 0;
    if (!LockLooper()) {
      return;
    }
    BRect c = ContentFrame();
    out_xywh[0] = c.left;
    out_xywh[1] = c.top;
    out_xywh[2] = c.Width() + 1;
    out_xywh[3] = c.Height() + 1;
    UnlockLooper();
  }

  void SetWindowTitle(const char* utf8) {
    if (!LockLooper()) {
      return;
    }
    BWindow::SetTitle(utf8);
    UnlockLooper();
  }

  void ZoomWindow() {
    if (!LockLooper()) {
      return;
    }
    BWindow::Zoom();
    UnlockLooper();
  }

  void MinimizeWindow(bool minimize) {
    if (!LockLooper()) {
      return;
    }
    BWindow::Minimize(minimize);
    UnlockLooper();
  }

  void ActivateWindow(bool active) {
    if (!LockLooper()) {
      return;
    }
    BWindow::Activate(active);
    UnlockLooper();
  }

  void PresentBitmap(BBitmap* bitmap,
                     float x,
                     float y,
                     float width,
                     float height) {
    if (!LockLooper()) {
      delete bitmap;
      return;
    }
    view_->SetFrontBuffer(bitmap);
    view_->Invalidate(BRect(x, y, x + width - 1, y + height - 1));
    UnlockLooper();
  }

  // Native toolbar state, pushed from Chromium's UI thread. Each takes the
  // window lock; no-ops when the window has no toolbar.
  void SetAddressText(const char* utf8) {
    if (chrome_ == NULL || !LockLooper()) {
      return;
    }
    chrome_->SetAddress(utf8);
    UnlockLooper();
  }

  void SetPageTitleText(const char* utf8) {
    if (chrome_ == NULL || !LockLooper()) {
      return;
    }
    chrome_->SetPageTitle(utf8);
    UnlockLooper();
  }

  void SetLoadingState(bool loading) {
    if (chrome_ == NULL || !LockLooper()) {
      return;
    }
    chrome_->SetLoading(loading);
    UnlockLooper();
  }

  void SetNavigationEnabled(bool back, bool forward) {
    if (chrome_ == NULL || !LockLooper()) {
      return;
    }
    chrome_->SetNav(back, forward);
    UnlockLooper();
  }

  void DestroyWindow() {
    // Quit() deletes the BWindow, and with it the views and this object.
    if (LockLooper()) {
      BWindow::Quit();
    }
  }

 private:
  Delegate* delegate_;
  // Window frame (screen coords) for a content rect: the toolbar strip sits
  // above the content, inside the same window, so the frame starts
  // kChromeHeight higher and the content keeps its own origin.
  static BRect WindowFrameForContent(BRect content, bool with_toolbar) {
    if (with_toolbar) {
      content.top -= kChromeHeight;
    }
    return content;
  }

  // The content view's rect in screen coordinates. Must hold the looper lock.
  BRect ContentFrame() {
    BRect f = Frame();
    if (with_toolbar_) {
      f.top += kChromeHeight;
    }
    return f;
  }

  // Moves a decorated window down/right so its tab and border are on screen.
  // Must hold the looper lock. FrameMoved() reports the result to Chromium.
  void KeepDecorOnScreen() {
    if (!has_frame_) {
      return;
    }
    float tab_height = 25.0f;
    float border = 5.0f;
    BMessage settings;
    if (GetDecoratorSettings(&settings) == B_OK) {
      BRect tab;
      if (settings.FindRect("tab frame", &tab) == B_OK && tab.IsValid()) {
        tab_height = tab.Height() + 1;
      }
      float b;
      if (settings.FindFloat("border width", &b) == B_OK && b > 0) {
        border = b;
      }
    }
    BRect f = Frame();
    float x = f.left < border ? border : f.left;
    float y = f.top < tab_height + border ? tab_height + border : f.top;
    if (x != f.left || y != f.top) {
      MoveTo(x, y);
    }
  }

  ShimView* view_ = NULL;
  BrowserChromeView* chrome_ = NULL;
  bool has_frame_ = false;
  bool with_toolbar_ = false;
};

}  // namespace

extern "C" void HaikuShimEnsureApp() {
  if (g_app_started) {
    return;
  }
  g_app_started = true;

  // Haiku's own semaphore rather than a Chromium primitive: this runs during
  // InitializeUI on the UI thread, where Chromium's thread restrictions
  // disallow blocking on a sync primitive.
  g_app_ready = create_sem(0, "haiku app ready");
  if (g_app_ready < B_OK) {
    return;
  }

  thread_id thread =
      spawn_thread(AppThreadEntry, "HaikuApp", B_NORMAL_PRIORITY, NULL);
  if (thread < B_OK) {
    delete_sem(g_app_ready);
    g_app_ready = -1;
    return;
  }
  resume_thread(thread);

  status_t status;
  do {
    status = acquire_sem(g_app_ready);
  } while (status == B_INTERRUPTED);
}

extern "C" NativeWindow* HaikuShimCreateWindow(float x,
                                               float y,
                                               float width,
                                               float height,
                                               bool has_frame,
                                               bool with_toolbar,
                                               Delegate* delegate) {
  BRect frame(x, y, x + width - 1, y + height - 1);
  return new ShimWindow(frame, has_frame, with_toolbar, delegate);
}

extern "C" void HaikuShimScreenFrame(float out_xywh[4]) {
  BScreen screen(B_MAIN_SCREEN_ID);
  BRect f = screen.Frame();
  out_xywh[0] = f.left;
  out_xywh[1] = f.top;
  out_xywh[2] = f.Width() + 1;
  out_xywh[3] = f.Height() + 1;
}

}  // namespace haiku_shim
