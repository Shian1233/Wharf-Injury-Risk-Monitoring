/** Implements the supplied ChatFlow Adapter API. Host platform can use its existing ChatFlow. */
export class RiskAgentAdapter {
  constructor({baseURL='/api',getToken=()=>'',getFilters=()=>({})}={}){Object.assign(this,{baseURL,getToken,getFilters})}
  async request(path,method='GET',body){const token=this.getToken();const r=await fetch(this.baseURL+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();if(!r.ok)throw new Error(data.detail||'请求失败');return data}
  async sendMessage(params){return this.request('/chat','POST',{content:params.content,sessionId:params.sessionId||'',filters:this.getFilters()})}
  async getHistory({page=1,pageSize=20,keyword=''}={}){const all=await this.request('/history');const items=all.filter(s=>s.title.includes(keyword));return {list:items.slice((page-1)*pageSize,page*pageSize).map(s=>({sessionId:s.id,title:s.title,answer:s.messages.at(-1)?.content||'',createTime:Date.parse(s.created_at),updateTime:Date.parse(s.updated_at||s.created_at),topFlag:s.pinned?2:1,isPinned:s.pinned,dayNum:Math.floor((Date.now()-Date.parse(s.created_at))/86400000)})),totalCount:items.length,totalPage:Math.ceil(items.length/pageSize),currentPage:page}}
  async deleteSession(ids){for(const id of Array.isArray(ids)?ids:[ids])await this.request('/history/'+id,'DELETE')}
  async pinSession(id,pin){return this.request('/history/'+id,'PATCH',{pinned:pin})}
  async renameSession(id,title){return this.request('/history/'+id,'PATCH',{title})}
}
