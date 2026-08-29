const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const GROUP_NAME = 'CCKTtCu9BFPHZTZC6L9Bdh'; // שם הקבוצה
const SHOP_URL = 'https://rare-licenses-base-stocks.trycloudflare.com/market';

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { args: ['--no-sandbox'] }
});

client.on('qr', qr => {
    console.log('סרוק QR:');
    qrcode.generate(qr, {small: true});
});

client.on('ready', async () => {
    console.log('✅ בוט מחובר!');
    const chats = await client.getChats();
    const group = chats.find(c => c.isGroup && c.name.includes('CCKT'));
    
    if(group){
        const msg = `🚀 *SLH MARKET נפתח* 🚀\n\n3 מוצרים - תשלום בTON:\n1. קורס AI - 15 TON\n2. בוט וואטסאפ - 10 TON\n3. VIP - 5 TON\n👉 ${SHOP_URL}\n\nקונים, משלמים, מקבלים גישה!`;
        await group.sendMessage(msg);
        console.log('✅ נשלח אוטומטי לקבוצה');
    } else {
        console.log('❌ לא מצא קבוצה');
    }
});

client.initialize();
