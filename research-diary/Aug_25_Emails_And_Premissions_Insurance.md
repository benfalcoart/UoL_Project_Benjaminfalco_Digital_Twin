## August 25, 2026 — Field Testing Locations and Research Permissions

Today I focused primarily on planning the field testing stage of the project and contacting potential locations where the BEHOLDER system could be tested in real-world environments.

I received a response from Grey Sauble Conservation Authority regarding my request to conduct field testing at Bruce's Caves Conservation Area. They indicated that they are receptive to the research and will prepare a standard research agreement for me to review. They also advised that research conducted on the property requires $5 million in liability insurance, with Grey Sauble Conservation Authority named as an additional insured.

I contacted the University of London to determine whether fieldwork conducted as part of an MSc final project may already be covered under an existing university liability insurance policy. I clarified that I am not requesting funding for insurance, but instead trying to determine whether existing university coverage applies before purchasing private insurance.

I also began expanding the list of potential field testing locations. An important consideration is obtaining datasets from different types of environments. Caves are particularly useful for testing the voxel-based volume estimation component because of their irregular geometry. However, they provide relatively little material diversity for the machine learning material classification component. Historic and industrial interiors should provide a much wider variety of visible materials, such as wood, stone, brick, metal, glass, plaster, and fabric.

Based on this, I decided that the field testing should ideally include both natural cave environments and indoor historic or industrial environments.

I contacted Scenic Caves Nature Adventures regarding the possibility of conducting field testing there. This location could potentially be incorporated into the same trip as Bruce's Caves, reducing the amount of additional travel required.

I also contacted several locations in the Niagara region regarding potential indoor field testing:

* Tintern Church of Christ
* The Brown Homestead
* Morningstar Mill
* Nelles Manor
* Beaverdams Church
* Niagara Railway Museum

For each location, I explained the project in nontechnical terms, described the portable camera equipment and how it would be used, and made it clear that nothing would be attached to or altered at the sites. I also asked whether they have research agreements, liability insurance requirements, or other conditions that would need to be met.

As a form of reciprocity, I offered to provide participating organizations with the resulting 3D models, photographs, and measurements if the captures are successful. I also offered to help make the resulting 3D models available as interactive models on their websites for educational purposes at no cost.

I discussed the project with my uncle, Garry Kennedy, who is a member of the Tintern Church of Christ congregation. He suggested that I contact the church regarding using its interior as a potential field testing location, so I included this connection when contacting them.

I considered several additional locations, including sites farther away in Ontario. However, because the project is approaching its final stages and I will be teaching during the week, I decided to prioritize locations within reasonable travelling distance. During the upcoming teaching term, Saturday through Tuesday will realistically be the available window for conducting fieldwork. Long-distance locations such as Thunder Bay are therefore unlikely to be practical for the MSc project and can instead remain potential locations for future work.

Rather than contacting every possible site immediately, I will wait to see how the current group responds. If there are few responses or several locations decline the request, I have identified additional heritage and museum sites in the Niagara region that I can contact.

The next steps are to wait for responses from the contacted locations, review the GSCA research agreement when it arrives, determine whether the University of London can provide liability coverage, and investigate private liability insurance if university coverage is unavailable. If private insurance is required by multiple locations, I will investigate whether a single short-term policy can cover field research at multiple sites and name the relevant organizations as additional insureds.

# Update — Niagara Railway Museum Approval

Later in the day, I received a response from Ken Jones, President of the Niagara Railway Museum, regarding my request to conduct field testing at the museum.

The museum has enthusiastically agreed to participate in the project and allow me to test the BEHOLDER system inside the museum. Saturdays will work best because the museum is open and staff are available. I will be able to conduct the capture while working around visitors.

This gives me my first confirmed external field testing location for the project.

The Niagara Railway Museum should be particularly useful for evaluating the material classification portion of the project. The museum is located in a former railway diesel shop and contains a variety of historic railway equipment and objects. This should provide a much greater variety of surfaces and materials than a cave environment and will allow me to test the system in a complex indoor environment.

Once the BEHOLDER hardware is ready for field testing, I will contact the museum again to arrange a specific Saturday. The only currently unavailable date mentioned by the museum is September 19.

This is a significant step toward real-world validation of the completed system and gives me a confirmed field site while I continue waiting for responses from the other locations contacted today.

# Update — Morningstar Mill Response

I also received a response from Carla Mackie, Historical Services Coordinator for the City of St. Catharines, regarding my request to conduct field testing at Morningstar Mill.

Carla confirmed that she received the research request and said that she personally likes the idea. She is currently away from the office and plans to follow up with me next week.

This is not yet formal approval to conduct the field testing, but it is a very positive initial response. I will wait for Carla's follow-up before making any plans for the site.

Morningstar Mill remains one of the more promising potential locations for testing the material classification portion of BEHOLDER. The historic mill environment should provide a mixture of different materials and surfaces within a relatively complex indoor space, making it substantially different from the cave environments being considered for volume and voxel-based analysis.

Combined with the confirmed cooperation from the Niagara Railway Museum, this response suggests that I should have access to at least one, and potentially several, suitable historic or industrial environments for real-world testing.

# BEHOLDER API Repository Update

Today I also reviewed the BEHOLDER API code that I wrote on August 20 and realized that I had forgotten to push it to the project repository. I reviewed the code and comments, made some minor documentation improvements, and pushed the API implementation to the repository.

No major functionality was added to the API today. This update primarily ensures that the work completed on August 20 is properly recorded in version control and included with the rest of the project.
