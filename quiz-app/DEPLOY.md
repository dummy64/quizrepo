# Deploying Quiz App on AWS EC2 (t3.micro)

## 1. Launch EC2 Instance

1. Go to **EC2 → Launch Instance** in AWS Console
2. Settings:
   - **Name**: `quiz-app`
   - **AMI**: Amazon Linux 2023
   - **Instance type**: `t3.micro` (free tier eligible)
   - **Key pair**: Create or select one (you'll need the `.pem` file to SSH)
   - **Security Group**: Create new with these inbound rules:

     | Type   | Port | Source    | Purpose       |
     |--------|------|-----------|---------------|
     | SSH    | 22   | Your IP   | SSH access    |
     | HTTP   | 80   | 0.0.0.0/0 | Web traffic   |
     | Custom | 3000 | 0.0.0.0/0 | Direct access (optional, remove after setting up nginx) |

   - **Storage**: 8 GB gp3 (default is fine)
3. Click **Launch Instance**

## 2. Allocate a Static IP (Elastic IP)

Without this, your IP changes every time the instance stops/starts.

1. Go to **EC2 → Elastic IPs → Allocate Elastic IP address**
2. Click **Allocate**
3. Select the new Elastic IP → **Actions → Associate Elastic IP address**
4. Choose your `quiz-app` instance → **Associate**

Your instance now has a fixed public IP. Note it down — e.g. `3.110.xxx.xxx`.

## 3. SSH into the Instance

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ec2-user@3.110.xxx.xxx
```

## 4. Install Node.js

```bash
sudo dnf update -y
sudo dnf install -y nodejs git
node -v  # should show v18+
```

## 5. Clone and Setup the App

```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo/quiz-app
npm install --production
```

## 6. Set Environment Variables

```bash
cat <<'EOF' > .env
OPENAI_API_KEY=sk-your-actual-key
PORT=3000
QUIZ_TOPIC=general knowledge and tech trivia
EOF
```

Then export them for the process:

```bash
export $(cat .env | xargs)
```

## 7. Test It

```bash
node server.js
```

Open `http://3.110.xxx.xxx:3000` in your browser. If it works, kill it (`Ctrl+C`) and proceed to run it properly.

## 8. Run with systemd (Keeps It Running)

Create a service file:

```bash
sudo tee /etc/systemd/system/quiz-app.service <<EOF
[Unit]
Description=Quiz App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/your-repo/quiz-app
EnvironmentFile=/home/ec2-user/your-repo/quiz-app/.env
ExecStart=/usr/bin/node server.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable quiz-app
sudo systemctl start quiz-app
sudo systemctl status quiz-app   # should show "active (running)"
```

Useful commands:

```bash
sudo systemctl restart quiz-app   # restart after code changes
sudo journalctl -u quiz-app -f    # view logs
```

## 9. Setup Nginx (Serve on Port 80)

So users can access `http://3.110.xxx.xxx` without the `:3000`.

```bash
sudo dnf install -y nginx
sudo tee /etc/nginx/conf.d/quiz.conf <<'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo rm -f /etc/nginx/conf.d/default.conf
sudo systemctl enable nginx
sudo systemctl start nginx
```

Now `http://3.110.xxx.xxx` works on port 80.

You can remove the port 3000 rule from your security group after this.

## 10. (Optional) Point a Domain

If you have a domain (e.g. `quiz.yourcompany.com`):

1. In your DNS provider, add an **A record**: `quiz.yourcompany.com → 3.110.xxx.xxx` (your Elastic IP)
2. Update the nginx config `server_name` to `quiz.yourcompany.com`
3. Restart nginx: `sudo systemctl restart nginx`

### Add HTTPS with Let's Encrypt

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d quiz.yourcompany.com
```

Certbot auto-renews via a systemd timer.

## Updating the App

```bash
cd ~/your-repo
git pull
cd quiz-app
npm install --production
sudo systemctl restart quiz-app
```

## Cost

- **t3.micro**: Free tier for 12 months, ~$8.50/month after
- **Elastic IP**: Free while associated with a running instance, $3.65/month if instance is stopped
- **Storage**: 8 GB gp3 = ~$0.64/month
- **Data transfer**: Negligible for this use case

Total: **Free (first year)** or **~$13/month** after.
