const API="/api";

function show(id){
    document.querySelectorAll("main section")
    .forEach(x=>x.classList.add("hidden"));

    document.getElementById(id)
    .classList.remove("hidden");
}


async function load(){

try{

let h = await fetch(API+"/health");
let health = await h.json();

document.getElementById("health").innerHTML =
"🟢 "+health.status;


let s = await fetch(API+"/stats");
let stats = await s.json();

users.innerHTML = stats.users || 0;
agents.innerHTML = stats.agents || 0;
tasks.innerHTML = stats.tasks || 0;


agents-data.innerHTML = JSON.stringify(
await (await fetch(API+"/agents")).json(),
null,2);


tasks-data.innerHTML = JSON.stringify(
await (await fetch(API+"/tasks")).json(),
null,2);


logs-data.innerHTML = JSON.stringify(
await (await fetch(API+"/logs")).json(),
null,2);


}catch(e){

document.getElementById("health").innerHTML=
"🔴 API ERROR";

}

}

load();
