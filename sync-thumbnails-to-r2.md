# Sync Thumbnails to Cloudflare R2

Instructions for uploading `thumb.webp` files from your personal laptop.

---

## What you're uploading

- **7,826 files** named `thumb.webp` (300x300 WebP, ~10-15KB each, ~100MB total)
- Located in `data/images/cameras/{Brand}/{Model}/thumb.webp`
- These are referenced by `landing.json` and served via the R2 CDN

---

## Step 1: Copy the thumbnail files to your personal laptop

On your corp laptop, zip up just the thumbnails:

```bash
cd ~/world-analogue-photography-museum
zip -r thumbnails.zip data/images/cameras/*/*/thumb.webp
```

This produces `thumbnails.zip` (~80-100MB). Transfer it to your personal laptop via AirDrop, USB drive, cloud storage, etc.

On your personal laptop, unzip it into a working directory:

```bash
mkdir -p ~/r2-upload
cd ~/r2-upload
unzip /path/to/thumbnails.zip
```

You should now have `~/r2-upload/data/images/cameras/{Brand}/{Model}/thumb.webp`.

---

## Step 2: Install rclone

### macOS

```bash
brew install rclone
```

### Linux

```bash
curl https://rclone.org/install.sh | sudo bash
```

### Windows

Download from https://rclone.org/downloads/

Verify installation:

```bash
rclone version
```

---

## Step 3: Get your R2 credentials

1. Go to **Cloudflare Dashboard** -> **R2** -> **Manage R2 API Tokens**
2. **Rotate your existing token** (the old one was exposed in shell history)
3. Create a new token with **Object Read & Write** permission for your bucket
4. Note down:
   - **Access Key ID**
   - **Secret Access Key**
   - **Account ID** (visible in the R2 overview page URL or sidebar)
   - **Bucket name** (the bucket where images are stored)

---

## Step 4: Configure rclone

Run the interactive setup:

```bash
rclone config
```

Follow the prompts:

1. `n` (new remote)
2. Name: `r2`
3. Storage type: `s3` (find it in the list, or type the number)
4. Provider: `Cloudflare`
5. Access Key ID: *(paste from step 3)*
6. Secret Access Key: *(paste from step 3)*
7. Region: leave blank, press Enter
8. Endpoint: `https://<YOUR_ACCOUNT_ID>.r2.cloudflarestorage.com`
9. Accept defaults for remaining options
10. `y` to confirm, `q` to quit config

Verify it works:

```bash
rclone lsd r2:<YOUR_BUCKET_NAME>
```

This should list the top-level directories in your bucket (you should see `images/`).

---

## Step 5: Dry run (preview what will be uploaded)

```bash
cd ~/r2-upload
rclone copy data/images/cameras/ r2:<YOUR_BUCKET_NAME>/images/cameras/ \
  --include "thumb.webp" \
  --dry-run \
  --progress
```

Verify it shows ~7,826 files to transfer and no unexpected paths.

---

## Step 6: Upload

```bash
cd ~/r2-upload
rclone copy data/images/cameras/ r2:<YOUR_BUCKET_NAME>/images/cameras/ \
  --include "thumb.webp" \
  --progress \
  --transfers 16
```

- `--transfers 16` runs 16 parallel uploads (speeds things up significantly)
- Should take a few minutes on a decent connection

---

## Step 7: Verify

Check a few files are accessible via your public R2 URL:

```bash
# Replace with your actual CDN base URL
curl -I "https://pub-YOUR_ID.r2.dev/images/cameras/Canon/Canon%20AE-1/thumb.webp"
```

You should get a `200 OK` with `content-type: image/webp`.

You can also count uploaded thumbnails:

```bash
rclone ls r2:<YOUR_BUCKET_NAME>/images/cameras/ --include "thumb.webp" | wc -l
```

Should show ~7,826.

---

## Step 8: Rebuild & redeploy the site

Back on your corp laptop (or wherever you deploy from):

```bash
cd ~/world-analogue-photography-museum/web
npm run build
```

Then deploy as usual. The landing page tiles will now load `thumb.webp` (~10KB) instead of `main.jpg` (~85KB).

---

## Cleanup

On your personal laptop, you can delete the upload directory:

```bash
rm -rf ~/r2-upload
rm /path/to/thumbnails.zip
```

Optionally remove the rclone config if you won't need it again:

```bash
rclone config delete r2
```
