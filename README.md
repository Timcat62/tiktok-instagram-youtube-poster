# 🎬 Social Poster

Publish **one video** to **YouTube (Shorts)**, **Instagram (Reels)** and **TikTok** in one go, with **the same description, hashtags and cover**.

![Preview](docs/screenshot.png)

- 📥 Drag and drop a **vertical or horizontal** video (MP4, MOV, WEBM, MKV…).
- 🖼️ Pick the **cover from the video's own frames** (slider, frame by frame, or thumbnail strip).
- 📱 **Horizontal videos are converted to 9:16** so they are published as **YouTube Shorts** (blurred background, black bars or center crop). You can also apply that format to Instagram and TikTok.
- ✅ **Tick or untick** platforms: post to one, two or all three. Platforms you haven't set up are simply greyed out.
- 🔒 Everything runs **on your computer**. Your login tokens stay in the `data/` folder, which is never pushed to GitHub.

---

## ⚠️ Read this first

Each platform requires you to create a free **"developer app"** under your name. It takes 10 to 20 minutes per platform, once. The platforms impose a few limits; the tool can't work around them:

| Platform | Limit |
|---|---|
| **YouTube** | Videos uploaded by **unaudited** Google projects are locked to **private**. To publish publicly, request a [YouTube API audit](https://support.google.com/youtube/contact/yt_api_form). It's free and takes a few days to a few weeks. The default quota allows a handful of uploads per day. |
| **Instagram** | Your account must be **professional** (Creator or Business) and **linked to a Facebook Page**. The API allows at most 100 posts per 24 h. The login lasts **60 days**; after that, just click "Reconnect". |
| **TikTok** | Until your TikTok app **is audited**, your TikTok account must be **private** and videos are posted as **"Only me"**. After the audit, you can choose any visibility. Workaround that needs no audit: **Draft** mode sends the video to your TikTok inbox so you can post it from the app. |

Other platform rules:
- **YouTube Shorts**: 3 minutes max. Longer videos are published as regular videos.
- **Instagram Reels**: 3 seconds to 15 minutes, captions up to 2,200 characters and 30 hashtags.

---

## Installation

1. Install **Python 3.10 or newer**: <https://www.python.org/downloads/>. On Windows, tick **"Add python.exe to PATH"**.
2. Download this project: green **Code → Download ZIP** button, then unzip it. Or run `git clone https://github.com/Timcat62/tiktok-instagram-youtube-poster.git`.
3. Start the app:
   - **Windows**: double-click `run.bat`
   - **macOS / Linux**: run `./run.sh` in a terminal

The first time, dependencies install automatically. ffmpeg is included, so there's nothing else to install. The interface then opens in your browser at <http://localhost:8765>.

> Keep the terminal window open while you use the app.

---

## Account setup

Everything happens in the app's **Accounts** tab. You **only need to set up the platforms you use**.

### YouTube

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project (for example "Social Poster").
2. **APIs & Services → Library**: search for **YouTube Data API v3** and click **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External**.
   - Fill in the app name and your email.
   - Under **Audience** (or "Test users"), add your Gmail address.
   - Click **Publish app** to switch it to *In production*. Otherwise Google logs the app out **every 7 days**. You don't need Google to verify the app: it will just show an "unverified app" warning. Click *Advanced → Go to …*.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - Download the JSON file.
5. In the app, click **Import client_secret.json**, then **Connect my channel**. A Google page opens: sign in and accept.
6. *(Optional, to publish publicly)* Request the [YouTube API audit](https://support.google.com/youtube/contact/yt_api_form).

> **Custom thumbnails**: your channel must be phone-verified (<https://www.youtube.com/verify>). Without it, the video is still published, but without the chosen cover. On Shorts, YouTube may also show its own frame in the Shorts feed.

### Instagram

**Requirement**: an Instagram account that is **Professional** (Settings → Account type → Creator or Business) and **linked to a Facebook Page** (from the Page: Settings → Linked accounts → Instagram).

1. Go to [Meta for Developers](https://developers.facebook.com/apps/) and click **Create app**.
   - Use case: **Other**, then type **Business**. Depending on the interface, the use case may be called "Manage messaging & content on Instagram".
2. In the app dashboard, add these products:
   - **Instagram**, choosing **"API setup with Facebook login"** (not "Instagram login").
   - **Facebook Login** (or "Facebook Login for Business").
3. **Facebook Login → Settings → Valid OAuth Redirect URIs**: add
   `http://localhost:8765/auth/instagram/callback`
   *(in development mode, Meta often allows `localhost` automatically)*
4. **App settings → Basic**: copy the **App ID** and **App Secret** into the app, then click **Save**.
5. Click **Connect with Facebook**. When Facebook asks, allow **your Page** and **your Instagram account**.

Your app can stay in **Development mode**. You can still post to your own account, since you're the app's admin.

**Plan B**: if the redirect login doesn't work, open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your app and generate a *User Token* with the permissions `instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management`. Then paste it into "Plan B": it is automatically converted into a 60-day token.

### TikTok

1. Go to [TikTok for Developers](https://developers.tiktok.com/apps/), sign in and click **Create app**. An organization or an individual account both work.
2. Platform: tick **Desktop**.
3. Add these products:
   - **Login Kit**: under *Redirect URI → Desktop*, add `http://localhost:8765/auth/tiktok/callback/` (with the trailing `/`).
   - **Content Posting API**: enable **Direct Post**.
4. Scopes: `user.info.basic`, `video.publish`, `video.upload`.
5. To test **without waiting for the audit**: open the **Sandbox** tab, create a sandbox, and add your TikTok account under **Target users**. Then use the sandbox's *Client key* and *Client secret*.
6. Set your TikTok account to **private** (TikTok app → Settings → Privacy → Private account) until the app is audited.
7. In the app: enter the **Client key** and **Client secret**, click **Save**, then **Connect TikTok**.

To publish publicly, submit your app for review (*Submit for review*) in the TikTok portal. The demo videos they ask for can be screen recordings of this tool. Once the app is approved, replace the sandbox keys with the production keys.

---

## Usage

1. Open **Publish** and drop your video.
2. Pick the **cover** with the slider, the ◀ ▶ buttons (or ← → on the keyboard), or the thumbnails.
3. If the video is horizontal, choose how the Short should look (live preview).
4. Write the **title** (YouTube only), the **description** and the **hashtags** (with or without `#`, separated by spaces). The final caption is `description + hashtags` and is the same on all three platforms.
5. Tick the platforms you want and click **Publish**. Each platform runs on its own: if one fails, the others keep going.

Your draft (title, description, hashtags) and your choices (ticked platforms, visibility…) are remembered in your browser.

## How it works

| | YouTube | Instagram | TikTok |
|---|---|---|---|
| API | YouTube Data API v3 (`videos.insert`) | Graph API (Reels, resumable upload) | Content Posting API (Direct Post or Inbox) |
| Cover | Frame extracted and uploaded as the thumbnail (`thumbnails.set`) | `thumb_offset` (frame position in ms) | `video_cover_timestamp_ms` |
| Horizontal video | Converted to 1080×1920 → Short | As is (or 9:16 if the option is ticked) | As is (or 9:16 if the option is ticked) |
| Hashtags | In the description + as tags | In the caption | In the caption |

If a file isn't compatible with Instagram (codec, 4K, over 60 fps, MKV/WEBM container…), it is automatically re-encoded to an H.264 MP4. Imported videos are deleted automatically after 7 days (`data/uploads`).

## Troubleshooting

- **"Python was not found"**: reinstall Python and tick *Add to PATH*.
- **Port 8765 is already in use**: change the port with the `PORT` variable, for example `set PORT=8800` then `run.bat`. The Instagram/TikTok redirect URIs must then use the same port.
- **YouTube: "access_denied"**: your address isn't in the test users, or the app isn't published.
- **YouTube: video is "private (locked)"**: that's the limit for unaudited projects (see above).
- **Instagram: "No professional Instagram account found"**: the account isn't professional, isn't linked to a Page, or the Page wasn't selected during login. Reconnect and tick everything.
- **TikTok: `unaudited_client_can_only_post_to_private_accounts`**: set your TikTok account to private, or use Draft mode.
- **TikTok: invalid redirect_uri**: check the exact URI, including the trailing `/`.

## Customizing the project

```
app.py              Local web server (Flask) + routes
poster/video.py     ffmpeg: probing, frames, 9:16 conversion
poster/youtube.py   YouTube login + publishing
poster/instagram.py Instagram login + publishing
poster/tiktok.py    TikTok login + publishing
poster/jobs.py      Parallel publishing with progress tracking
static/             Interface (plain HTML/CSS/JS, no framework)
data/               Your settings and tokens (created at launch, ignored by git)
```

To add a platform: create `poster/<platform>.py` with `status()` and `publish(...)`, then wire it into `jobs.py`, `app.py` and `static/`.

Contributions are welcome (issues and pull requests).

## License

[MIT](LICENSE): free to use, modify and redistribute.
