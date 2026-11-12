import type {ReactNode} from 'react';
import { CircleDashed } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
export function Pill({children,tone='neutral'}:{children:ReactNode;tone?:'neutral'|'good'|'warn'|'danger'}){return <Badge variant="outline" className={`pill ${tone}`}><span className="pill-dot"/>{children}</Badge>}
export function Panel({children,className=''}:{children:ReactNode;className?:string}){return <Card className={`panel ${className}`}>{children}</Card>}
export function Empty({title,detail}:{title:string;detail:string}){return <div className="empty-state"><CircleDashed className="empty-symbol" aria-hidden="true" size={25}/><strong>{title}</strong><p>{detail}</p></div>}
export function Time({value}:{value?:string}){return <time title={value}>{value?new Date(value).toLocaleString():'Not recorded'}</time>}
export function SectionHeading({eyebrow,title,detail,aside}:{eyebrow?:string;title:string;detail?:string;aside?:ReactNode}){return <div className="section-heading"><div>{eyebrow&&<span className="overline">{eyebrow}</span>}<h2>{title}</h2>{detail&&<p>{detail}</p>}</div>{aside}</div>}
export function NumberTile({label,value,detail,tone='neutral'}:{label:string;value:string|number;detail:string;tone?:'neutral'|'good'|'warn'|'danger'}){return <div className={`number-tile ${tone}`}><span className="overline">{label}</span><strong>{value}</strong><small>{detail}</small></div>}
