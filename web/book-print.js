'use strict';
document.getElementById('printBook').addEventListener('click',async()=>{
  await Promise.all([...document.images].map(img=>img.decode().catch(()=>{})));
  window.print();
});
