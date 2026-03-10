[0:03] Them: Here, just give me one second. So make your bundle. Yeah.

[0:11] You: Should be good. Yeah.

[0:09] Them: So excited to have you work trial. I'll send you over. something over chat shortly. Essentially you're going to be building our or recreating a reconciliation engine which reconciles bank transactions to explanation of benefits that we pull in from on the payer portals, so we have normalized data, of bank transactions, so the accrued amount when the bank transaction was posted to the bank. And, um... EOB data, normalized data, So like how much the payment, adjustment is any adjustments that were on the payment. You'll have the bank transaction notes, And essentially the idea is to reconcile those two things and create a join of them and then anything that cannot be reconciled, you surface a task. That's kind of what what our product does currently. That's kind of the... the take on that you'll be working on here. I have it ready.

[1:18] You: Okay. Okay. Mm-hmm.

[1:20] Them: I'll wormhole you it in a second. Yeah.

[1:23] You: Okay, sure. So, sorry. Oh, sorry. Go ahead.

[1:26] Them: No, ask any questions.

[1:29] You: Yeah, you just said all the ones you can non-reconceal. What do I do with them? Sorry.

[1:35] Them: The ones that we cannot reconcile? We surface them in our dashboard. tasks for the users of our product to follow up manually. So if they receive a payment in their account that we cannot find like a, like a, like a, a corresponding like EOB for, then we have like, Hey, we noticed this insurance payment. We don't have like a PDF for this payments, like, can you look at this?

[2:06] You: Yeah, human. Okay. Yeah. Okay. Okay.

[2:06] Them: manually. Yes. All right. Any questions for me or? Well, I...

[2:19] You: Okay, sounds good. So can we use

[2:21] Them: Thank you. Yes, so you're... The prompt is, I sent it in chat if you want to download. The prompt is very open. you can use LLMs, you can adjust how it works, how it works, how it works, works is we bundled in a year's worth of kind of obfuscated transaction data and some normalized payment

[2:43] You: LLM for the reconciliation, right? Okay.

[2:46] Them: and your task is to, you know, complete that data. We're going to internally test that again and it's like a full complete set of data. afterwards, so obviously do not overlook

[2:55] You: Okay, the real data.

[2:58] Them: overfitted to what you've been provided. You can assume that there's like infrastructure structures such as task queues or a crons, something like that. Yeah, I would just focus on like good systems design, think about how you would make a performance, how you you might handle multi-tenancy money counts, that sort of thing. the general like to see like which trade-offs that you make because there's a ton to make here with the heuristics that you can choose to determine whether or not a transaction and a payment, sorry, a transaction in an EOB map.

[3:38] You: Okay. Okay. Yeah.

[3:41] Them: that sort of thing. Yeah, so you can use LLMs. AI assistance, web, things fair game, we're just kind of focusing more on like high level level of trade offs that you make and. if you can make something that works for

[3:56] You: Yeah. Yeah. Yeah. Yeah. Okay.

[3:59] Them: share. It doesn't need to be like 100% accurate, but, you know, focus on, like, good... system design principles, making it performant, Yeah. But how about it? I'm on email. if you want to ever ask any questions.

[4:16] You: Mm-hmm. So, yeah. You okay?

[4:18] Them: We're doing this until 6 o'clock. a bundle of zip and then send it over to me via wormhole. or email or whatever is most convenient to you. Any questions? Do you want to run through the prompt? quick together

[4:30] You: Okay. Yeah, let me... Let's take a look at the brown wormhole. Interesting.

[4:39] Them: Sorry, we didn't do intros, but I want to give you as much time as possible.

[4:43] You: No, I'm perfect with that, too.

[4:45] Them: Yeah.

[4:48] You: So the bromp is in the ring, I guess I'm saying that.

[4:48] Them: Yes.

[4:57] You: Yeah. Okay. That's a big one. Yeah. Yeah.

[4:58] Them: Ja, Robin. Great, let me just step through it with you. All right. Our goal is to like, build an AI platform that runs the dental office right now what we do is Posting which is kind of writing like. reconciled statements of payments from dental insurers into a practices database. The prompt is to implement a reconciliation engine to match bank transactions to payment records. So in EOB, is kind of a breakdown of a payment which has an amount, a payment to dates, and a number that the payer decides on, as a payment type, not entirely relevant

[5:45] You: Yeah, I have it open, yeah. Yeah, yeah.

[5:47] Them: here, but you have like a bank transaction, hopefully that's self-explanatory, It's a record. It can be either positive or negative sum within the actual accounts. Reconciliation is difficult because the notes on the transactions don't always contain complete Sometimes they're just the name of the pair, or MetLife or just contain random numbers in them, or a lot of a lot of the time, like the accounts that people use for their insurance payments are just the regular business accounts. So you'll see stuff for payroll, rents,

[6:22] You: Okay, okay. Yeah. Okay.

[6:24] Them: I've seen like the. One of our customers had like a Porsche payments on there, you know, It's just a bunch of random crap is in there. I kind of work with that. Your task is to build the the reconciliation engine that. Creates the join of these two tables and then also creates reasonable tasks for the practice to follow up on. It's important that you're not producing too much noise to the practice and giving them A TASK TO FOLLOW UP ON IF IT'S THEIR PORSCH PAM.

[6:56] You: Okay, okay. Okay, okay. Yeah.

[6:57] Them: You have to think about what do I surface, what's worth it, surfacing, that sort of thing. Right. There's two types of tasks. There's a... a bank transaction task and a payment an EOB missing bank transaction task. Right. Some rules, you have complete freedom You can restructure files at tables or columns to the ORM that we gave you. So we use Python

[7:23] You: Mhm. Yeah. Okay. Missing you. Okay. Mhm.

[7:25] Them: and Django here at C4C, so we should like SQLite with the stub data and then Also... like Pee Wee Orm, which is kind of like the Django Orm. basic selects, joins, where it causes. Here's the through tables you have, you have payers with which represent a canonicalized view of the different insurance providers there are, bank transactions, EOBs, which are those payment records. Right, and then there's a dashboard that you can fully around with, which just has like three views on it. There's the payments, which are the joint views, and then there's the which contains the tasks separate to interview two tabs, if you run like a Poe or So you probably want to use UBSYNC dash dash and include all or all extras, sorry, and then you can do a Poe dashboard and it'll pop up a

[8:20] You: Okay. Okay. Okay. Okay.

[8:20] Them: little dashboard with a few tabs that you can click on. That kind of uses a dummy engine. That just returns like random data. Yeah. Um... Any questions or questions?

[8:33] You: Okay. Okay. Okay. Okay. Sounds good.

[8:36] Them: If you want to get cracking.

[8:37] You: Yeah, I think I can start and email you. if I run into some issues, I guess. Yeah.

[8:42] Them: OK. I will keep an eye on my inbox. I usually don't do a good job of that, but I will, I will make sure that like, you know, I'm looking at my inbox over the Cobb Minister. Usually I'm on Slack, but you're not on the Slack.

[8:55] You: Yeah. Okay. Yeah, same, same.

[8:57] Them: I will have my email open. and just try to make sure that I'm quick Yeah, but have fun with it. There's no like immense amount of pressure here. It's just like probably good system design.

[9:11] You: Thank you. Yeah. Yeah. Sounds good.

[9:13] Them: Yeah, sounds good.

[9:15] You: Okay. Thank you. Thank you. See you later. Bye.

[9:16] Them: Bye-bye.