const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');

const GROUP_ID = '120363xxxxxxxxxx@g.us'; // נחליף ל-ID של CCKTtCu9BFPHZTZC6L9Bdh
const SHOP_URL = 'https://rare-licenses-base-stocks.trycloudflare.com/market';

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { args: ['--no-sandbox'] }
});

client.on('qr', qr => {
    console.log('סרוק QR פעם אחת:');
    qrcode.generate(qr, {small: true});
});

client.on('ready', async () => {
    console.log('✅ בוט וואטסאפ מחובר!');
    
    // שליחה אוטומטית לקבוצה כל שעה
    const message = `🚀 *SLH MARKET* 🚀\n\n3 מוצרים חדשים - תשלום בTON:\n\n1. קורס AI Automation - 15 TON\n2. בוט וואטסאפ מוכן - 10 TON\n3. מנוי VIP חודשי - 5 TON\n👉 ${SHOP_URL}/market\n\nקונים, משלמים, מקבלים גישה מיידית!`;
    
    // שלח עכשיו
    await client.sendMessage(GROUP_ID, message);
    console.log('✅ פורסם אוטומטי לקבוצה');
    
    // ואז כל 4 שעות
    setInterval(async () => {
        await client.sendMessage(GROUP_ID, message);
        console.log('✅ פורסם שוב אוטומטי');
    }, 4 * 60 * 60 * 1000);
});

client.initialize();
