'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const context={};vm.createContext(context);
vm.runInContext(source.match(/const norm=.*;/)[0]+source.slice(source.indexOf('function searchLabor('),source.indexOf('function renderLabor(')),context);
const rows=[
 {code:'60007',description:'INSTALAR ESTRUTURA CONCRETO'},
 {code:'7200',description:'INSTALAR TRANSFORMADOR 75 KVA'},
 {code:'12',description:'RETIRAR ESTRUTURA CONCRETO'},
 {code:'600070',description:'SERVIÇO SEM NOME',search:'NOME INEXISTENTE'}
];
assert.equal(context.searchLabor(rows,'60007')[0].code,'60007');
assert.equal(context.searchLabor(rows,'estrutura concreto').length,2);
assert.equal(context.searchLabor(rows,'instalár transformador 75')[0].code,'7200');
assert.equal(context.searchLabor(rows,'NOME INEXISTENTE').length,0);
assert.equal(context.searchLabor(rows,'  ').length,rows.length);
console.log('Busca por nome/código, acentos, termos combinados e prioridade de código: OK');
